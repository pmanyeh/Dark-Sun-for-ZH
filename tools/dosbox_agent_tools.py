import subprocess
import threading
import time
import re
from typing import Dict, Any

class DOSBoxXDebuggerBridge:
    """
    DOSBox-X 核心底層橋接器：
    負責管理 DOSBox-X 行程，並透過標準輸入輸出（stdio）與除錯器命令列（T->）互動。
    """
    def __init__(self, dosbox_path: str = "dosbox-x"):
        # 啟動命令包含 -debug 模式，並利用 -dorefldebug 將除錯器介面反射到標準輸出
        self.process = subprocess.Popen(
            [dosbox_path, "-debug", "-dorefldebug"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        self.output_buffer = ""
        self.lock = threading.Lock()
        
        # 啟動背景執行緒即時接收除錯器的純文字輸出
        self.read_thread = threading.Thread(target=self._read_output, daemon=True)
        self.read_thread.start()
        
        # 稍微等待 DOSBox-X 啟動初始化完成
        time.sleep(1.0)

    def _read_output(self):
        while True:
            line = self.process.stdout.readline()
            if line:
                with self.lock:
                    self.output_buffer += line
            else:
                break

    def execute_command(self, cmd: str, wait_time: float = 0.2) -> str:
        """對除錯器底層輸入框（T->）發送指令，並擷取回傳的除錯文字"""
        with self.lock:
            self.output_buffer = ""
            
        self.process.stdin.write(cmd + "\n")
        self.process.stdin.flush()
        
        # 留一點時間讓除錯器處理硬體狀態變更（例如單步執行或記憶體讀取）
        time.sleep(wait_time)
        
        with self.lock:
            return self.output_buffer

    def parse_registers(self, raw_text: str) -> Dict[str, str]:
        """
        輔助函數：將除錯器回傳的亂雜純文字，使用正規表示式（Regex）過濾，
        精準轉換為 AI 最愛的 JSON/Dict 格式，省下大量 Token 並防止 AI 幻覺。
        """
        regs = {}
        # 匹配如 EAX=00000000, CS=F000, EIP=0000FFF0 等 16/32 位元暫存器數值
        pattern = r"([A-Z]{2,3})=([0-9A-Fa-f]+)"
        matches = re.findall(pattern, raw_text)
        for reg, val in matches:
            regs[reg] = val
        return regs


# =====================================================================
# 1. 封裝給 OpenAI 體系（GPT-4o、LangChain、AutoGPT）使用的 Tool 定義
# =====================================================================

# 實例化底層橋接器
dbx_bridge = DOSBoxXDebuggerBridge()

# 這是提供給大模型的 Functions 清單定義（Tools Schema）
OPENAI_DOSBOX_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "dosbox_debugger_step",
            "description": "在 DOSBox-X 除錯器中執行單步除錯（對應 T 或 P 指令）。AI 需要追蹤當前 CPU 暫存器變化時使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "use_proceed": {
                        "type": "boolean",
                        "description": "是否使用 Proceed (P) 跳過副程式（Call）？若為 false 則使用 Trace (T) 進入副程式內部。"
                    }
                },
                "required": ["use_proceed"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dosbox_debugger_read_memory",
            "description": "讀取 DOS 虛擬記憶體區段內的數值（對應 D 指令），可用於檢視資料檢視區（Data view）或變數狀態。",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "要讀取的記憶體段落與偏移地址，例如 'DS:0000' 或 'F000:E05B'"
                    }
                },
                "required": ["address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "dosbox_debugger_set_breakpoint",
            "description": "在指定的記憶體代碼位置設定中斷點（對應 BP 指令），程式執行到該處時會自動暫停。",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "中斷點目標地址，例如 'CS:FFF0'"
                    }
                },
                "required": ["address"]
            }
        }
    }
]

# 當 AI 決定呼叫某個工具時，Python 控制端執行的對應實作邏輯
def handle_openai_tool_call(tool_name: str, arguments: dict) -> Dict[str, Any]:
    if tool_name == "dosbox_debugger_step":
        cmd = "p" if arguments.get("use_proceed") else "t"
        raw_out = dbx_bridge.execute_command(cmd)
        # 單步執行後，自動幫 AI 整理最新的暫存器狀態回傳
        parsed_regs = dbx_bridge.parse_registers(raw_out)
        return {"status": "Success", "current_registers": parsed_regs, "raw_output": raw_out}
        
    elif tool_name == "dosbox_debugger_read_memory":
        addr = arguments.get("address")
        raw_out = dbx_bridge.execute_command(f"d {addr}")
        return {"status": "Success", "memory_dump": raw_out}
        
    elif tool_name == "dosbox_debugger_set_breakpoint":
        addr = arguments.get("address")
        raw_out = dbx_bridge.execute_command(f"bp {addr}")
        return {"status": "Success", "debugger_message": raw_out}
        
    return {"status": "Error", "message": "Unknown tool call"}


# =====================================================================
# 2. 封裝給 Anthropic 體系（Claude Code、Cursor、Cline）使用的 MCP Server 格式
# =====================================================================
# 如果你的 Agent 工具鏈完全走 Anthropic 推廣的 MCP（Model Context Protocol）標準，
# 你可以使用以下對接方式（基於標準 JSON-RPC 響應格式封裝）：

def get_mcp_tool_definitions():
    """回傳符合 MCP 標準的 Tools 宣告"""
    return [
        {
            "name": "dosbox_mcp_execute",
            "description": "直接對 DOSBox-X 內建除錯器發送任何原生 T-> 命令列指令，並獲取最新的硬體/暫存器終端回傳文字。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "原生的 DOSBox-X 除錯器指令。例如 'r' 查看暫存器, 't' 單步, 'g' 繼續運行, 'sm DS:0000 55' 修改記憶體。"
                    }
                },
                "required": ["command"]
            }
        }
    ]

def handle_mcp_tool_call(name: str, arguments: dict):
    """處理 Claude Agent 的 MCP 工具呼叫"""
    if name == "dosbox_mcp_execute":
        cmd = arguments.get("command")
        raw_output = dbx_bridge.execute_command(cmd)
        
        # 依照 MCP 協議標準，必須將結果包裝在 content 的 text 欄位中回傳
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"[DOSBox-X Debugger Response for '{cmd}']:\n{raw_output}"
                }
            ]
        }
    return {"isError": True, "content": [{"type": "text", "text": "Tool not found"}]}
