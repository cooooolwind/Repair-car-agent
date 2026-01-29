// minimal-connect.js
const sdk = require("@autoxing/robot-js-sdk");
const { AXRobot, AppMode } = sdk;

const APP_ID = "axb0c00f331c594dc1";
const APP_SECRET = "0b713d93ec50419197f0e0cd66556f0d";
const ROBOT_ID = "2682407903593VX";
const SERVER_URL = "https://api.autoxing.com/";
const WS_URL = "wss://service.autoxing.com/";

(async function () {
  const axRobot = new AXRobot(
    APP_ID,
    APP_SECRET,
    AppMode.WAN_APP,
    SERVER_URL,
    WS_URL
  );

  const ok = await axRobot.init();
  if (!ok) return;

  await axRobot.connectRobot({ robotId: ROBOT_ID });

  // const state = await axRobot.getState();
  // const { list = [] } = await axRobot.getPoiList({ robotId: ROBOT_ID });

  // const targets = list
  //   .filter(p => p.areaId === state.areaId)
  //   .filter(p => (p.name ?? "").trim() !== "")
  //   .map(p => ({ name: p.name, id: p.id, type: p.type, x: p.coordinate?.[0], y: p.coordinate?.[1], yaw: p.yaw }));

  // console.log(targets);

  
  // 进入控制模式
  await axRobot.beginControl();

  // 给一个明显的目标
  await axRobot.moveTo({
    x: 1.8475,
    y: 4.12,
    yaw: 358
  });

  // 结束控制
  await axRobot.endControl();

})();