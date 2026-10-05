// GET  /api/favorites —— 收藏列表（记录表读取）
// POST /api/favorites —— 添加收藏（记录表写入，★Day 18 核心知识点）
//
// 同一个函数按 HTTP 方法分流：GET 读、POST 写。
// POST 防「重复收藏」两层：应用层先查后插（给中文提示）+ 数据库 UNIQUE(poem_id) 约束兜底（防并发漏判）。
//
// 响应统一 { ok, data, error } 三字段。

const cloudbase = require('@cloudbase/node-sdk');

const ENV_ID = 'shijishanhe-d5gmc8a0k01b1e88d';

exports.main = async (event, context) => {
  const headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  // 兼容多种网关触发格式，取 HTTP 方法
  const method = (
    event.httpMethod ||
    (event.requestContext && event.requestContext.httpMethod) ||
    (event.requestContext && event.requestContext.http && event.requestContext.http.method) ||
    'GET'
  ).toUpperCase();

  // CORS 预检请求直接放行
  if (method === 'OPTIONS') {
    return { statusCode: 204, headers, body: '' };
  }

  try {
    const app = cloudbase.init({ env: ENV_ID });
    const db = app.rdb({ database: 'public' });

    if (method === 'POST') {
      return await handlePost(event, db, headers);
    }
    return await handleGet(db, headers);
  } catch (err) {
    console.error('[api-favorites] 未捕获异常:', err);
    return { statusCode: 500, headers, body: JSON.stringify({ ok: false, data: null, error: '服务器内部错误' }) };
  }
};

// ---------- GET：读取收藏列表 ----------
async function handleGet(db, headers) {
  const { data, error } = await db
    .from('favorites')
    .select('id, poem_id, created_at, poems(title, poets(name, dynasty))')
    .order('created_at', { ascending: false });

  if (error) {
    console.error('[api-favorites] GET 查询失败:', error);
    return { statusCode: 500, headers, body: JSON.stringify({ ok: false, data: null, error: String(error.message || error) }) };
  }

  const list = (data || []).map((r) => ({
    id: r.id,
    poem_id: r.poem_id,
    title: (r.poems && r.poems.title) || '',
    poet: (r.poems && r.poems.poets && r.poems.poets.name) || '',
    dynasty: (r.poems && r.poems.poets && r.poems.poets.dynasty) || '',
    created_at: r.created_at,
  }));

  return { statusCode: 200, headers, body: JSON.stringify({ ok: true, data: list, error: null }) };
}

// ---------- POST：添加收藏 ----------
async function handlePost(event, db, headers) {
  // 1) 解析请求体（兼容 base64 编码）
  let body = {};
  try {
    let raw = event.body || '{}';
    if (event.isBase64Encoded && typeof raw === 'string') {
      raw = Buffer.from(raw, 'base64').toString('utf-8');
    }
    body = JSON.parse(raw);
  } catch (e) {
    console.log('[api-favorites] POST 拒绝：请求体不是合法 JSON');
    return { statusCode: 400, headers, body: JSON.stringify({ ok: false, data: null, error: '请求体不是合法的 JSON' }) };
  }

  const poemIdRaw = body.poem_id;

  // 2) 必填字段校验（缺 / 非数字 → 中文提示）
  if (poemIdRaw === undefined || poemIdRaw === null || poemIdRaw === '') {
    console.log('[api-favorites] POST 拒绝：缺少必填字段 poem_id');
    return { statusCode: 400, headers, body: JSON.stringify({ ok: false, data: null, error: '缺少必填字段 poem_id（诗词 ID）' }) };
  }
  const poemId = Number(poemIdRaw);
  if (!Number.isInteger(poemId) || poemId <= 0) {
    console.log('[api-favorites] POST 拒绝：poem_id 非法 =', poemIdRaw);
    return { statusCode: 400, headers, body: JSON.stringify({ ok: false, data: null, error: 'poem_id 必须是正整数' }) };
  }

  // 3) 诗词是否存在（不存在 → 中文提示）
  const { data: poem, error: poemErr } = await db
    .from('poems')
    .select('id')
    .eq('id', poemId)
    .maybeSingle();
  if (poemErr) {
    console.error('[api-favorites] 查询诗词失败:', poemErr);
    return { statusCode: 500, headers, body: JSON.stringify({ ok: false, data: null, error: '服务器内部错误' }) };
  }
  if (!poem) {
    console.log('[api-favorites] POST 拒绝：诗词不存在 id =', poemId);
    return { statusCode: 404, headers, body: JSON.stringify({ ok: false, data: null, error: '该诗词不存在' }) };
  }

  // 4) 防重复（第一层：应用层先查后插）
  const { data: existed } = await db
    .from('favorites')
    .select('id')
    .eq('poem_id', poemId)
    .maybeSingle();
  if (existed) {
    console.log('[api-favorites] POST 拒绝：已收藏过 poem_id =', poemId);
    return { statusCode: 409, headers, body: JSON.stringify({ ok: false, data: null, error: '已收藏过这首诗' }) };
  }

  // 5) 插入（第二层：数据库 UNIQUE(poem_id) 约束兜底，防并发重复）
  const { error: insErr } = await db.from('favorites').insert({ poem_id: poemId });
  if (insErr) {
    // PostgreSQL 唯一约束冲突错误码 23505；PostgREST 也可能返回 409 文案
    if (String(insErr.code) === '23505' || /duplicate|unique|已存在/i.test(String(insErr.message || insErr))) {
      console.log('[api-favorites] POST 拒绝（唯一约束兜底）：poem_id =', poemId);
      return { statusCode: 409, headers, body: JSON.stringify({ ok: false, data: null, error: '已收藏过这首诗' }) };
    }
    console.error('[api-favorites] 插入失败:', insErr);
    return { statusCode: 500, headers, body: JSON.stringify({ ok: false, data: null, error: '写入失败：' + String(insErr.message || insErr) }) };
  }

  // 6) 查回刚插入的记录（poem_id 唯一，正好定位到新行）
  const { data: created } = await db
    .from('favorites')
    .select('id, poem_id, created_at')
    .eq('poem_id', poemId)
    .maybeSingle();

  console.log('[api-favorites] POST 成功：新增收藏 id =', created && created.id, 'poem_id =', poemId);
  return {
    statusCode: 200,
    headers,
    body: JSON.stringify({
      ok: true,
      data: {
        id: created && created.id,
        poem_id: poemId,
        created_at: created && created.created_at,
      },
      error: null,
    }),
  };
}
