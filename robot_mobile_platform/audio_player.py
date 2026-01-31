# audio_player.py
import subprocess
import json

def play_audio(audio_url: str) -> dict:
    """
    极简版本：播放音频
    """
    try:
        # 执行JavaScript文件
        result = subprocess.run(
            ["node", "audio_play.js", audio_url],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # 返回执行结果
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

# 使用示例
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        url = sys.argv[1]
        result = play_audio(url)
        print(json.dumps(result, indent=2))