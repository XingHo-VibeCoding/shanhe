// /api/ink —— 诗中有画 · 一句一画（内容 + 点赞/收藏/浏览量）
//
// GET  /api/ink            —— 画作列表（画廊用：标题/作者/封面/计数，不含大字段 content）
// GET  /api/ink?slug=xxx   —— 单篇完整内容（content JSON 已解析）+ 当前计数
// POST /api/ink            —— 计数 +1 { slug, action: 'view' | 'like' | 'fav' }，返回新计数
//
// 计数说明：本项目暂无用户登录体系，like/fav 是全站累计值；
// 防连点由前端 localStorage 负责，服务端只做参数校验。
// 写入采用「先读后写」，量级小（个位数并发）下足够可靠。
//
// 响应统一 { ok, data, error } 三字段（与 api-favorites / api-checkins 一致）。

const cloudbase = require('@cloudbase/node-sdk');

const ENV_ID = 'shijishanhe-d5gmc8a0k01b1e88d';

const VALID_ACTIONS = ['view', 'like', 'fav'];

exports.main = async (event) => {
  const headers = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
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

    const qs = (event && (event.queryStringParameters || event.queryString)) || {};
    let body = {};
    try {
      let raw = event.body || '{}';
      if (event.isBase64Encoded && typeof raw === 'string') {
        raw = Buffer.from(raw, 'base64').toString('utf-8');
      }
      body = JSON.parse(raw);
    } catch (e) {
      body = {};
    }

    if (method === 'GET') {
      return await handleGet(qs, db, headers);
    }
    if (method === 'POST') {
      return await handlePost(body, db, headers);
    }
    return bad(headers, 405, '不支持的请求方法：' + method);
  } catch (err) {
    console.error('[api-ink] 未捕获异常:', err);
    return { statusCode: 500, headers, body: JSON.stringify({ ok: false, data: null, error: '服务器内部错误' }) };
  }
};

function bad(headers, code, msg) {
  return { statusCode: code, headers, body: JSON.stringify({ ok: false, data: null, error: msg }) };
}

function parseContent(row) {
  try {
    return JSON.parse(row.content);
  } catch (e) {
    return null;
  }
}

// ---------- GET：列表 / 单篇 ----------
async function handleGet(qs, db, headers) {
  const slug = String(qs.slug || '').trim();

  // 单篇：?slug=xxx
  if (slug) {
    const { data, error } = await db.from('ink_pages').select('*').eq('slug', slug).maybeSingle();
    if (error) {
      console.error('[api-ink] GET 单篇查询失败:', error);
      return bad(headers, 500, '数据暂时不可用，请稍后再试');
    }
    if (!data) {
      return bad(headers, 404, '没有找到这幅「一句一画」：' + slug);
    }
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({
        ok: true,
        data: {
          id: data.id,
          slug: data.slug,
          title: data.title,
          poet: data.poet,
          dynasty: data.dynasty,
          form: data.form,
          cover_path: data.cover_path,
          lede: data.lede,
          content: parseContent(data),
          views: data.views,
          likes: data.likes,
          favs: data.favs,
          updated_at: data.updated_at,
        },
        error: null,
      }),
    };
  }

  // 列表：画廊用，不取 content 大字段
  const { data, error } = await db
    .from('ink_pages')
    .select('id, slug, title, poet, dynasty, form, cover_path, views, likes, favs, created_at')
    .order('created_at', { ascending: false });
  if (error) {
    console.error('[api-ink] GET 列表失败:', error);
    return bad(headers, 500, '数据暂时不可用，请稍后再试');
  }
  return { statusCode: 200, headers, body: JSON.stringify({ ok: true, data: data || [], error: null }) };
}

// ---------- POST：计数 +1 ----------
async function handlePost(body, db, headers) {
  const slug = String(body.slug || '').trim();
  const action = String(body.action || '').trim();

  if (!slug) {
    return bad(headers, 400, '缺少必填字段 slug（画作标识）');
  }
  if (slug.length > 100) {
    return bad(headers, 400, 'slug 过长（最多 100 字符）');
  }
  if (VALID_ACTIONS.indexOf(action) === -1) {
    return bad(headers, 400, "action 必须是 'view' / 'like' / 'fav' 之一");
  }

  // 1) 先确认存在并读当前计数
  const { data: row, error: selErr } = await db
    .from('ink_pages')
    .select('id, views, likes, favs')
    .eq('slug', slug)
    .maybeSingle();
  if (selErr) {
    console.error('[api-ink] POST 查询失败:', selErr);
    return bad(headers, 500, '服务器内部错误');
  }
  if (!row) {
    return bad(headers, 404, '没有找到这幅「一句一画」：' + slug);
  }

  // 2) 计数 +1（先读后写）
  const patch = {};
  if (action === 'view') patch.views = Number(row.views || 0) + 1;
  if (action === 'like') patch.likes = Number(row.likes || 0) + 1;
  if (action === 'fav') patch.favs = Number(row.favs || 0) + 1;

  const { error: updErr } = await db.from('ink_pages').update(patch).eq('slug', slug);
  if (updErr) {
    console.error('[api-ink] POST 更新失败:', updErr);
    return bad(headers, 500, '写入失败，请稍后再试');
  }

  // 3) 读回最新计数返回（眼见为实）
  const { data: fresh } = await db
    .from('ink_pages')
    .select('views, likes, favs')
    .eq('slug', slug)
    .maybeSingle();

  console.log('[api-ink] POST', slug, action, '→', JSON.stringify(fresh));
  return { statusCode: 200, headers, body: JSON.stringify({ ok: true, data: { slug, action, ...fresh }, error: null }) };
}
