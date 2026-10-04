-- ============================================================
-- 诗迹山河 · 数据表结构（三张核心表）
-- 数据库：CloudBase PostgreSQL
-- 可重复执行：先 DROP 后 CREATE（按外键依赖逆序删除）
-- ============================================================

-- ---------- 先删（逆序：先删引用表，再删被引用表） ----------
DROP TABLE IF EXISTS favorites;
DROP TABLE IF EXISTS poems;
DROP TABLE IF EXISTS poets;

-- ---------- 后建 ----------

-- 1. 作者表 poets：存「作者是谁」
CREATE TABLE poets (
  id        SERIAL PRIMARY KEY,
  name      TEXT NOT NULL UNIQUE,
  dynasty   TEXT,
  intro     TEXT
);

-- 2. 诗词表 poems：存「每首诗的内容」
CREATE TABLE poems (
  id            SERIAL PRIMARY KEY,
  title         TEXT NOT NULL,
  poet_id       INTEGER NOT NULL REFERENCES poets(id),
  dynasty       TEXT,
  content       TEXT,
  translation   TEXT,
  annotation    TEXT,
  background    TEXT,
  appreciation  TEXT,
  popularity    BIGINT NOT NULL DEFAULT 0,
  CONSTRAINT popularity_non_negative CHECK (popularity >= 0)
);

-- 3. 收藏记录表 favorites：存「用户收藏行为」
CREATE TABLE favorites (
  id          SERIAL PRIMARY KEY,
  poem_id     INTEGER NOT NULL REFERENCES poems(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 收藏按诗查询 / 按时间倒序读取，建索引提速
CREATE INDEX IF NOT EXISTS idx_favorites_poem_id ON favorites(poem_id);
CREATE INDEX IF NOT EXISTS idx_favorites_created_at ON favorites(created_at);

-- ---------- 表注释 ----------
COMMENT ON TABLE poets IS '作者表：存作者是谁（姓名 / 朝代 / 简介）';
COMMENT ON TABLE poems IS '诗词表：存每首诗的内容（五件套 + 背景 + 赏析）';
COMMENT ON TABLE favorites IS '收藏记录表：存用户收藏了哪些诗（poem_id 关联 poems.id）';

-- ---------- 字段注释（余力加练：解释每个字段类型为什么这么选） ----------
COMMENT ON COLUMN poets.id IS '作者唯一标识，主键，SERIAL 自增不重复';
COMMENT ON COLUMN poets.name IS '作者姓名，TEXT 变长、UNIQUE 保证不重复';
COMMENT ON COLUMN poets.dynasty IS '朝代，短文本用 TEXT 最省心';
COMMENT ON COLUMN poets.intro IS '作者生平简介，TEXT 不设长度上限';

COMMENT ON COLUMN poems.id IS '诗词唯一标识，主键，SERIAL 自增不重复';
COMMENT ON COLUMN poems.title IS '诗名，TEXT（同名诗很多，故不加 UNIQUE）';
COMMENT ON COLUMN poems.poet_id IS '作者 ID，外键关联 poets.id，NOT NULL 保证每首诗必有作者';
COMMENT ON COLUMN poems.dynasty IS '朝代，TEXT';
COMMENT ON COLUMN poems.content IS '原文，TEXT（可能较长）';
COMMENT ON COLUMN poems.translation IS '译文，TEXT，可能为空';
COMMENT ON COLUMN poems.annotation IS '注释，TEXT，可能为空';
COMMENT ON COLUMN poems.background IS '创作背景，TEXT';
COMMENT ON COLUMN poems.appreciation IS '赏析，TEXT';
COMMENT ON COLUMN poems.popularity IS '知名度，BIGINT 数值很大（名篇上亿）故用 8 字节整数';

COMMENT ON COLUMN favorites.id IS '收藏记录唯一标识，主键，SERIAL 自增';
COMMENT ON COLUMN favorites.poem_id IS '被收藏的诗词 ID，外键关联 poems.id';
COMMENT ON COLUMN favorites.created_at IS '收藏时间，TIMESTAMPTZ 带时区，默认当前时间';
