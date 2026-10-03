// /api/health 健康检查云函数（Day 15，云函数网关版）
// 这是 CloudBase 的「Event 函数」+ HTTP 访问服务（云函数网关）。
// 通过公网网关访问时，函数入口返回「状态码 + 响应头 + 正文」三件套。
// 职责：只回答「服务是否活着」，不处理任何业务。

exports.main = async (event, context) => {
  // 1) 组装要返回的数据
  const data = {
    status: 'ok',                    // 探活结论：正常
    service: 'shiji-shanhe-api',     // 服务名，方便确认是谁在回话
    time: new Date().toISOString(),  // 服务器当前时间，证明是「现在」真跑出来的
  };

  // 2) 按云函数网关规范返回三件套
  return {
    statusCode: 200,                               // HTTP 200 = 成功
    headers: { 'Content-Type': 'application/json' }, // 告诉浏览器这是 JSON
    body: JSON.stringify(data),                    // 把对象转成 JSON 字符串作为正文
  };
};
