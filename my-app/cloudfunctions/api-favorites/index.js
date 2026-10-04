// GET /api/favorites —— 收藏列表（记录表读取，★Day 17 核心知识点）
// favorites 表只有 poem_id（外键数字），没有 title/poet 这些人类可读字段。
// 因此必须 JOIN：favorites.poem_id → poems.id → poems.poet_id → poets.id，
// 把 poem_id 翻译成 title（诗名）和 poet（作者名），才能满足接口契约。
// 这就是「接口要返回的字段，表里不一定有，得靠外键 JOIN 补出来」。

const cloudbase = require('@cloudbase/node-sdk');

const ENV_ID = 'shijishanhe-d5gmc8a0k01b1e88d';

exports.main = async (event, context) => {
  const headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
  };

  try {
    const app = cloudbase.init({ env: ENV_ID });
    // 我们的表建在 public schema；rdb() 默认把 schema 设成 envId 会报 Invalid schema
    const db = app.rdb({ database: 'public' });

    // 嵌套 JOIN：favorites → poems（title）→ poets（name/dynasty）
    const { data, error } = await db
      .from('favorites')
      .select('id, poem_id, created_at, poems(title, poets(name, dynasty))')
      .order('created_at', { ascending: false });

    if (error) {
      return { statusCode: 500, headers, body: JSON.stringify({ ok: false, error: String(error.message || error) }) };
    }

    const list = (data || []).map((r) => ({
      id: r.id,
      poem_id: r.poem_id,
      title: (r.poems && r.poems.title) || '',
      poet: (r.poems && r.poems.poets && r.poems.poets.name) || '',
      dynasty: (r.poems && r.poems.poets && r.poems.poets.dynasty) || '',
      created_at: r.created_at,
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
