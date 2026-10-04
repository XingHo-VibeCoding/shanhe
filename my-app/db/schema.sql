-- ============================================================
-- 诗迹山河 · 数据表结构（Day 16）
-- 数据库：CloudBase PostgreSQL
-- 核心：两张表，靠 poems.poet_id -> poets.id 关联（一对多）
-- 说明：本文件可重复执行（CREATE TABLE IF NOT EXISTS + COMMENT 幂等）
-- ============================================================

-- 1. 作者表：存「作者是谁」
CREATE TABLE IF NOT EXISTS poets (
  id        SERIAL PRIMARY KEY,
  name      TEXT NOT NULL UNIQUE,
  dynasty   TEXT,
  intro     TEXT
);

-- 2. 诗词表：存「每首诗的内容」
CREATE TABLE IF NOT EXISTS poems (
  id            SERIAL PRIMARY KEY,
  title         TEXT NOT NULL,
  poet_id       INTEGER REFERENCES poets(id),
  dynasty       TEXT,
  content       TEXT,
  translation   TEXT,
  annotation    TEXT,
  background    TEXT,
  appreciation  TEXT,
  popularity    BIGINT DEFAULT 0
);

-- 3. 表注释
COMMENT ON TABLE poets IS '作者表：存作者是谁（姓名 / 朝代 / 简介）';
COMMENT ON TABLE poems IS '诗词表：存每首诗的内容（五件套 + 背景 + 赏析）';

-- 4. 字段注释（余力加练：解释每个字段类型为什么这么选）
COMMENT ON COLUMN poets.id IS '作者唯一标识，主键，SERIAL 自增不重复';
COMMENT ON COLUMN poets.name IS '作者姓名，TEXT 变长、UNIQUE 保证不重复';
COMMENT ON COLUMN poets.dynasty IS '朝代，短文本用 TEXT 最省心';
COMMENT ON COLUMN poets.intro IS '作者生平简介，TEXT 不设长度上限';

COMMENT ON COLUMN poems.id IS '诗词唯一标识，主键，SERIAL 自增不重复';
COMMENT ON COLUMN poems.title IS '诗名，TEXT';
COMMENT ON COLUMN poems.poet_id IS '作者 ID，INTEGER 外键关联 poets.id，只存数字最省最快';
COMMENT ON COLUMN poems.dynasty IS '朝代，TEXT';
COMMENT ON COLUMN poems.content IS '原文，TEXT（可能较长）';
COMMENT ON COLUMN poems.translation IS '译文，TEXT，可能为空';
COMMENT ON COLUMN poems.annotation IS '注释，TEXT，可能为空';
COMMENT ON COLUMN poems.background IS '创作背景，TEXT';
COMMENT ON COLUMN poems.appreciation IS '赏析，TEXT';
COMMENT ON COLUMN poems.popularity IS '知名度，BIGINT 数值很大（名篇上亿）故用 8 字节整数';
