// /api/checkins —— 诗词学习打卡记录（Day 22：增删改查四类操作闭环）
//
// GET    /api/checkins          —— 打卡列表（JOIN poems 带出诗名/作者）
// POST   /api/checkins          —— 新增打卡 { poem_id, status?, note? }
// PATCH  /api/checkins?id=N     —— 修改一条 { status?, note? }（★Day 22 新增）
// DELETE /api/checkins?id=N     —— 删除一条（★Day 22 新增）
//   id 也可用路径传：/api/checkins/12；PATCH 也可放 body.id
//
// 知识点（今日一问）：删除比新增容易出事，因为新增最多多一条脏数据，
// 删错了数据直接消失且不可逆。所以本函数所有写操作都遵循同一套防御：
//   1) id 必填且必须是正整数（否则 400 中文提示）
//   2) 先 SELECT 确认存在（不存在 404，绝不静默成功）
//   3) 操作后把受影响的记录返回给调用方，眼见为实
//
// 响应统一 { ok, data, error } 三字段。

const cloudbase = require('@cloudbase/node-sdk');

const ENV_ID = 'shijishanhe-d5gmc8a0k01b1e88d';

// 打卡状态的合法取值（与数据库 CHECK 约束一致）
const VALID_STATUS = ['学习中', '已完成'];

exports.main = async (event) => {
  const headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, PATCH, DELETE, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
  };

  const method = (
    event.httpMethod ||
    (event.requestContext && event.requestContext.httpMethod) ||
    (event.requestContext && event.requestContext.http && event.requestContext.http.method) ||
    'GET'
  ).toUpperCase();

  if (method === 'OPTIONS') {
    return { statusCode: 204, headers, body: '' };
  }

  try {
    const app = cloudbase.init({ env: ENV_ID });
    const db = app.rdb({ database: 'public' });

    // 解析查询参数与请求体（写法与 api-favorites 保持一致）
    const qs = (event && (event.queryStringParameters || event.queryString)) || {};
    let body = {};
    try {
      let raw = event.body || '{}';
      if (event.isBase64Encoded && typeof raw === 'string') {
        raw = Buffer.from(raw, 'base64').toString('utf-8');
      }
      body = JSON.parse(raw);
    } catch (e) {
      body = {}; // 交由各分支按需校验
    }

    // ---------- GET：打卡列表 ----------
    if (method === 'GET') {
      return await handleGet(db, headers);
    }

    // ---------- POST：新增打卡 ----------
    if (method === 'POST') {
      return await handlePost(body, db, headers);
    }

    // ---------- PATCH：修改一条（★Day 22 核心） ----------
    if (method === 'PATCH') {
      const id = resolveId(qs, body, event);
      if (id === null) {
        return bad(headers, 400, '缺少记录 id（可用 ?id=N、路径 /api/checkins/N 或 body.id 传入）');
      }
      return await handlePatch(id, body, db, headers);
    }

    // ---------- DELETE：删除一条（★Day 22 核心） ----------
    if (method === 'DELETE') {
      const id = resolveId(qs, body, event);
      if (id === null) {
        return bad(headers, 400, '缺少记录 id（可用 ?id=N、路径 /api/checkins/N 或 body.id 传入）');
      }
      return await handleDelete(id, db, headers);
    }

    return bad(headers, 405, '不支持的请求方法：' + method);
  } catch (err) {
    console.error('[api-checkins] 未捕获异常:', err);
    return { statusCode: 500, headers, body: JSON.stringify({ ok: false, data: null, error: '服务器内部错误' }) };
  }
};

// ---------- 工具：从 query / 路径 / body 三处解析 id ----------
function resolveId(qs, body, event) {
  const fromQs = Number(qs.id);
  if (Number.isInteger(fromQs) && fromQs > 0) return fromQs;
  const fromBody = Number(body.id);
  if (Number.isInteger(fromBody) && fromBody > 0) return fromBody;
  // 路径形如 /api/checkins/12
  const m = event && event.path && /\/api\/checkins\/(\d+)\/?$/.exec(event.path);
  if (m) return Number(m[1]);
  return null;
}

function bad(headers, code, msg) {
  return { statusCode: code, headers, body: JSON.stringify({ ok: false, data: null, error: msg }) };
}

// 校验 status 取值
function validStatus(s) {
  return VALID_STATUS.indexOf(s) !== -1;
}

// ---------- GET ----------
async function handleGet(db, headers) {
  const { data, error } = await db
    .from('checkins')
    .select('id, poem_id, status, note, created_at, poems(title, poets(name, dynasty))')
    .order('created_at', { ascending: false });

  if (error) {
    console.error('[api-checkins] GET 查询失败:', error);
    return bad(headers, 500, '数据暂时不可用，请稍后再试');
  }

  const list = (data || []).map((r) => ({
    id: r.id,
    poem_id: r.poem_id,
    title: (r.poems && r.poems.title) || '',
    poet: (r.poems && r.poems.poets && r.poems.poets.name) || '',
    dynasty: (r.poems && r.poems.poets && r.poems.poets.dynasty) || '',
    status: r.status,
    note: r.note || '',
    created_at: r.created_at,
  }));

  return { statusCode: 200, headers, body: JSON.stringify({ ok: true, data: list, error: null }) };
}

// ---------- POST ----------
async function handlePost(body, db, headers) {
  const poemId = Number(body.poem_id);
  if (!Number.isInteger(poemId) || poemId <= 0) {
    return bad(headers, 400, '缺少必填字段 poem_id（诗词 ID，正整数）');
  }
  const status = body.status === undefined ? '学习中' : body.status;
  if (!validStatus(status)) {
    return bad(headers, 400, 'status 只能是「学习中」或「已完成」');
  }
  const note = body.note === undefined ? null : String(body.note);

  // 诗词必须存在
  const { data: poem } = await db.from('poems').select('id').eq('id', poemId).maybeSingle();
  if (!poem) {
    return bad(headers, 404, '该诗词不存在');
  }

  const { data: created, error: insErr } = await db
    .from('checkins')
    .insert({ poem_id: poemId, status, note })
    .select('id, poem_id, status, note, created_at')
    .maybeSingle();
  if (insErr) {
    console.error('[api-checkins] 插入失败:', insErr);
    return bad(headers, 500, '写入失败，请稍后再试');
  }

  console.log('[api-checkins] POST 成功：id =', created && created.id);
  return { statusCode: 200, headers, body: JSON.stringify({ ok: true, data: created, error: null }) };
}

// ---------- PATCH（★Day 22） ----------
async function handlePatch(id, body, db, headers) {
  // 1) 校验要改的字段：status / note 至少给一个
  const hasStatus = body.status !== undefined;
  const hasNote = body.note !== undefined;
  if (!hasStatus && !hasNote) {
    return bad(headers, 400, 'PATCH 需要至少提供 status 或 note 之一');
  }
  let patch = {};
  if (hasStatus) {
    if (!validStatus(body.status)) {
      return bad(headers, 400, 'status 只能是「学习中」或「已完成」');
    }
    patch.status = body.status;
  }
  if (hasNote) {
    patch.note = body.note === null ? null : String(body.note);
  }

  // 2) 先查后改：id 不存在明确 404，不静默成功
  const { data: existed } = await db
    .from('checkins')
    .select('id, poem_id, status, note, created_at')
    .eq('id', id)
    .maybeSingle();
  if (!existed) {
    return bad(headers, 404, '打卡记录不存在（id=' + id + '）');
  }

  // 3) 执行更新并返回改后的记录（WHERE id 精确命中一条）
  const { data: updated, error: updErr } = await db
    .from('checkins')
    .update(patch)
    .eq('id', id)
    .select('id, poem_id, status, note, created_at')
    .maybeSingle();
  if (updErr) {
    console.error('[api-checkins] 更新失败:', updErr);
    return bad(headers, 500, '更新失败，请稍后再试');
  }

  console.log('[api-checkins] PATCH 成功：id =', id, '字段 =', Object.keys(patch).join(','));
  return {
    statusCode: 200,
    headers,
    body: JSON.stringify({ ok: true, data: { before: existed, after: updated }, error: null }),
  };
}

// ---------- DELETE（★Day 22） ----------
async function handleDelete(id, db, headers) {
  // 1) 先查后删：把将要消失的记录先取出来返回（删错了也能知道删的是什么）
  const { data: existed } = await db
    .from('checkins')
    .select('id, poem_id, status, note, created_at')
    .eq('id', id)
    .maybeSingle();
  if (!existed) {
    return bad(headers, 404, '打卡记录不存在（id=' + id + '），无需删除');
  }

  // 2) 执行删除（WHERE id 精确命中一条）
  const { error: delErr } = await db.from('checkins').delete().eq('id', id);
  if (delErr) {
    console.error('[api-checkins] 删除失败:', delErr);
    return bad(headers, 500, '删除失败，请稍后再试');
  }

  console.log('[api-checkins] DELETE 成功：id =', id);
  return { statusCode: 200, headers, body: JSON.stringify({ ok: true, data: { deleted: existed }, error: null }) };
}
