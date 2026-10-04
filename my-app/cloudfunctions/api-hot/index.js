// GET /api/hot —— 热门诗词榜（真实热搜数据）
// 读 CloudBase PostgreSQL 的 poems 表，按知名度 popularity 降序取 TOP N。
// 通过 @cloudbase/node-sdk 的 rdb() 访问关系型数据库（云函数内自动鉴权，无需连接串）。
// 响应格式对齐课程模板：{ ok: true, data: [...] }。

const cloudbase = require('@cloudbase/node-sdk');

const ENV_ID = 'shijishanhe-d5gmc8a0k01b1e88d'; // 环境 ID（公开信息，见 cloudbaserc.json）

exports.main = async (event, context) => {
  const headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
  };

  // 1) 解析查询参数（云函数网关把 query 放在 queryStringParameters，兼容 queryString）
  const qs = (event && (event.queryStringParameters || event.queryString)) || {};
  const rawLimit = parseInt(qs.limit, 10);
  const limit = Number.isFinite(rawLimit) ? Math.min(Math.max(rawLimit, 1), 50) : 10;

  try {
    // 2) 初始化 SDK 并取关系型数据库句柄
    const app = cloudbase.init({ env: ENV_ID });
    // 我们的表建在 public schema；rdb() 默认把 schema 设成 envId 会报 Invalid schema
    const db = app.rdb({ database: 'public' });

    // 3) 查 poems，按知名度降序，JOIN poets 带出作者名/朝代
    const { data, error } = await db
      .from('poems')
      .select('id, title, content, popularity, dynasty, poets(name, dynasty)')
      .order('popularity', { ascending: false })
      .order('id', { ascending: true })
      .limit(limit);

    if (error) {
      return { statusCode: 500, headers, body: JSON.stringify({ ok: false, error: String(error.message || error) }) };
    }

    // 4) 拍平外键嵌套字段，输出契约约定的字段
    const list = (data || []).map((r) => ({
      id: r.id,
      title: r.title,
      poet: (r.poets && r.poets.name) || '',
      dynasty: (r.poets && r.poets.dynasty) || r.dynasty || '',
      content: r.content || '',
      popularity: r.popularity,
    }));

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ ok: true, data: list }),
    };
  } catch (err) {
    return { statusCode: 500, headers, body: JSON.stringify({ ok: false, error: String(err && err.message) }) };
  }
};
