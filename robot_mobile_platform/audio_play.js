// audio_play.js
const sdk = require("@autoxing/robot-js-sdk");
const { AXRobot, AppMode } = sdk;

const APP_ID = "axb0c00f331c594dc1";
const APP_SECRET = "0b713d93ec50419197f0e0cd66556f0d";
const ROBOT_ID = "2682407903593VX";
const SERVER_URL = "https://api.autoxing.com/";
const WS_URL = "wss://service.autoxing.com/";

// 从命令行接收音频URL参数
const audioUrl = process.argv[2];

(async function () {
  try {
    if (!audioUrl) {
      console.log(JSON.stringify({ ok: false, err: "缺少音频URL参数" }));
      process.exit(1);
    }

    const axRobot = new AXRobot(
      APP_ID,
      APP_SECRET,
      AppMode.WAN_APP,
      SERVER_URL,
      WS_URL
    );

    const ok = await axRobot.init();
    if (!ok) {
      console.log(JSON.stringify({ ok: false, err: "SDK初始化失败" }));
      return;
    }

    await axRobot.connectRobot({ robotId: ROBOT_ID });
    
    let playAudio = {
      mode: 1,
      url: audioUrl,
      interval: -1,
      num: 1,
    };
    
    const success = await axRobot.setPlayAudio(playAudio);
    
    // 输出JSON格式结果，便于Python解析
    console.log(JSON.stringify({ 
      ok: success, 
      message: success ? "音频播放指令发送成功" : "音频播放指令发送失败",
      url: audioUrl
    }));
    
  } catch (error) {
    console.log(JSON.stringify({ 
      ok: false, 
      err: error.message || String(error) 
    }));
  }
})();