// move_to_poi.js
const sdk = require("@autoxing/robot-js-sdk");
const { AXRobot, AppMode } = sdk;

const APP_ID = "axb0c00f331c594dc1";
const APP_SECRET = "0b713d93ec50419197f0e0cd66556f0d";
const ROBOT_ID = "2682407903593VX";
const SERVER_URL = "https://api.autoxing.com/";
const WS_URL = "wss://service.autoxing.com/";

// 从命令行接收点名（Python 传进来）
const targetName = process.argv[2];
if (!targetName) {
  console.log(JSON.stringify({ ok: false, step: "args", errText: "no target name" }));
  process.exit(1);
}

(async () => {
  try {
    // 1️⃣ 创建 SDK 客户端
    const axRobot = new AXRobot(
      APP_ID,
      APP_SECRET,
      AppMode.WAN_APP,
      SERVER_URL,
      WS_URL
    );

    // 2️⃣ 初始化（鉴权 + 建立基础通信）
    const inited = await axRobot.init();
    if (!inited) {
      console.log(JSON.stringify({ ok: false, step: "init" }));
      return;
    }

    // 3️⃣ 连接指定机器人
    await axRobot.connectRobot({ robotId: ROBOT_ID });

    // 4️⃣ 读取当前状态，做安全检查
    const state = await axRobot.getState();
    if (state.isEmergencyStop) {
      console.log(JSON.stringify({ ok: false, step: "state", errText: "EmergencyStop=true" }));
      return;
    }
    if (state.isManualMode) {
      console.log(JSON.stringify({ ok: false, step: "state", errText: "ManualMode=true" }));
      //return;
    }

    // 5️⃣ 获取 POI 列表（地图点位）
    const { list = [] } = await axRobot.getPoiList({ robotId: ROBOT_ID });

    // ⚠️ 只按 name 匹配（如需更稳，可加 areaId 判断）
    const target = list.find(p => p.name === targetName);

    if (!target || !target.coordinate) {
      console.log(JSON.stringify({
        ok: false,
        step: "poi",
        errText: "target not found",
        targetName
      }));
      return;
    }

    // 6️⃣ 取目标位姿（地图绝对坐标）
    const x = target.coordinate[0];
    const y = target.coordinate[1];
    const yaw = target.yaw;

    // 7️⃣ 进入单车控制 → 下发 moveTo → 释放控制
    await axRobot.beginControl();
    const accepted = await axRobot.moveTo({ x, y, yaw });
    await axRobot.endControl();

    // 8️⃣ 输出结果（给 Python 解析）
    console.log(JSON.stringify({
      ok: !!accepted,
      mode: "moveTo",
      target: {
        name: target.name,
        id: target.id,
        x,
        y,
        yaw
      }
    }));

    process.exit(0);
  } catch (e) {
    console.log(JSON.stringify({
      ok: false,
      step: "exception",
      errText: String(e)
    }));
  }
})();
