// /api/health 健康检查云函数（CloudBase「Event 函数」+ 云函数网关）
// 职责：只回答「服务是否活着」，不连数据库、不写任何业务逻辑。
// 通过公网网关访问时，入口返回「状态码 + 响应头 + 正文」三件套。

exports.main = async (event, context) => {
  // 1) 组装探活结论
  const data = {
    ok: true,            // 探活结论：服务正常
    service: 'shanhe',   // 项目英文名（对应 GitHub 仓库 XingHo-VibeCoding/shanhe）
  };

  // 2) 按云函数网关规范返回三件套
  return {
    statusCode: 200,                                 // HTTP 200 = 成功
    headers: { 'Content-Type': 'application/json' }, // 告诉浏览器这是 JSON
    body: JSON.stringify(data),                      // 对象转 JSON 字符串作为正文
  };
};
