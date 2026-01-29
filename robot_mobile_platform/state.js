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

  const state = await axRobot.getState();
  console.log(state.x); // 位置坐标的 x 分量
  console.log(state.y); // 位置坐标的 y 分量  
})();
