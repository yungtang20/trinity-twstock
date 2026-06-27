# VibeCoding 线性框架 — 视频逐字稿

---

## 【开头钩子】0:00 - 1:00

你有没有遇到过这种情况——

你跟 AI 说"帮我做一个 xx 功能"，它噼里啪啦写了几百行代码，结果你一运行，全是报错。你再跟它说，它又改，改完又坏，坏了再改……十分钟过去了，你的项目还是原地踏步。

这不是 AI 不够聪明。

**这是你跟 AI 之间没有契约。**

AI 不知道你真正想做什么，不知道用什么技术，不知道哪些东西绝对不能动，不知道什么叫"完成"。所以它只能靠猜——然后你替它收拾残局。

今天我要介绍一套我自己设计的工作框架，叫做 **VibeCoding 线性框架**。

它做的事情只有一件：**在你和 AI 之间建立契约，让它按你说的来，不靠猜。**

用了这套框架之后，AI 不会再乱跑，不会在你还没想清楚的时候就开始写代码，不会把所有文档一次性塞进上下文然后开始混乱，也不会在你问它"现在到哪了"的时候给你一个莫名其妙的回答。

我们开始。

---

## 【整体架构介绍】1:00 - 3:30

先从全局看这套框架是什么结构。

它的核心思路就两个字：**线性**。

不是说项目不能改，而是说每次只做一件事，做完才能进入下一步。整个流程分七个阶段：

**第一阶段，PRD 规划。** 把你的想法变成一份清楚、可验收的产品需求文档。

**第二阶段，项目框架。** 决定用什么技术，目录怎么组织，模块怎么划分。

**第三阶段，交互逻辑。** 把每一个用户动作、系统反馈、状态流转都写清楚。

**第四阶段，前端交接包。** 生成一份可以直接扔给专业前端 AI 的自包含文档——它不需要读任何其他文件，只读这一份就能开工。

**第五阶段，前端生成代码。** 专业前端 AI 按交接包实现，不自己发挥。

**第六阶段，项目记录。** 把当前状态、版本变化、踩过的坑全部记下来，让下次对话能无缝接续。

**第七阶段，验收闸门。** 用脚本跑检查，用验收标准说话，不靠 AI 自我报告"完成了"。

这七个阶段，对应七类文件，由一个叫 `AGENTS.md` 的入口文件统一调度。

这是整套框架最重要的一个设计：**AI 每次启动只读一个文件。** 不是全部，是一个。然后这个文件告诉它现在在哪个阶段、该读哪些文件、用什么视角工作。

---

## 【完整交互流程图】

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #fff;
    color: #1a1a1a;
    padding: 24px 16px;
  }
  .diagram {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0;
    max-width: 680px;
    margin: 0 auto;
  }
  .entry-node {
    background: #2563eb;
    color: #fff;
    border-radius: 10px;
    padding: 10px 28px;
    font-size: 13px;
    font-weight: 700;
    text-align: center;
    width: 260px;
  }
  .arrow {
    width: 2px;
    height: 22px;
    background: #d1d5db;
    position: relative;
    margin: 0 auto;
  }
  .arrow::after {
    content: '';
    position: absolute;
    bottom: -5px;
    left: 50%;
    transform: translateX(-50%);
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #d1d5db;
  }
  .phase-row {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    justify-content: center;
  }
  .phase {
    border: 1.5px solid #d1d5db;
    border-radius: 10px;
    padding: 10px 14px;
    width: 200px;
    background: #fff;
  }
  .phase.active {
    border-color: #2563eb;
    background: #eff6ff;
  }
  .phase-label { font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 3px; }
  .phase-title { font-size: 14px; font-weight: 700; color: #1a1a1a; margin-bottom: 4px; }
  .phase.active .phase-title { color: #2563eb; }
  .phase-file { font-size: 11px; color: #6b7280; font-family: monospace; background: #f3f4f6; border-radius: 4px; padding: 1px 5px; display: inline-block; margin-top: 2px; }
  .phase-desc { font-size: 11px; color: #6b7280; margin-top: 5px; line-height: 1.5; }
  .side-note-box {
    background: #f9fafb;
    border: 1.5px dashed #e5e7eb;
    border-radius: 8px;
    padding: 7px 10px;
    font-size: 11px;
    color: #6b7280;
    line-height: 1.5;
    width: 140px;
  }
  .side-note-box.warn { border-color: #f59e0b; background: #fffbeb; color: #92400e; }
  .connector-h { width: 24px; height: 1.5px; background: #d1d5db; position: relative; }
  .connector-h::after { content: ''; position: absolute; right: -5px; top: 50%; transform: translateY(-50%); border-top: 5px solid transparent; border-bottom: 5px solid transparent; border-left: 6px solid #d1d5db; }
  .gate { background: #16a34a; color: #fff; border-radius: 10px; padding: 10px 20px; text-align: center; width: 200px; }
  .gate-title { font-size: 13px; font-weight: 700; }
  .gate-sub { font-size: 11px; opacity: 0.85; margin-top: 3px; }
  .legend { display: flex; gap: 20px; margin-top: 20px; flex-wrap: wrap; justify-content: center; }
  .legend-item { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #6b7280; }
  .legend-dot { width: 10px; height: 10px; border-radius: 2px; }
</style>
</head>
<body>
<div class="diagram">

  <div class="entry-node">AGENTS.md<br><span style="font-size:10px;font-weight:400;opacity:.85">唯一入口 · 状态路由</span></div>
  <div class="arrow"></div>

  <div class="phase-row">
    <div style="width:170px"></div>
    <div class="phase active">
      <div class="phase-label">Step 1</div>
      <div class="phase-title">PRD 规划</div>
      <div class="phase-file">PRD.md</div>
      <div class="phase-desc">定位 · 用户 · P0 · 验收标准</div>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <div class="connector-h"></div>
      <div class="side-note-box">确认定位 + P0<br>验收标准<br>→ 才能推进</div>
    </div>
  </div>
  <div class="arrow"></div>

  <div class="phase-row">
    <div style="width:170px"></div>
    <div class="phase">
      <div class="phase-label">Step 2</div>
      <div class="phase-title">项目框架</div>
      <div class="phase-file">PROJECT_FRAME.md</div>
      <div class="phase-desc">技术栈 · 模块边界 · 数据模型</div>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <div class="connector-h"></div>
      <div class="side-note-box warn">⚠️ 全栈项目<br>需锁定 API 方向<br>再进 Step 3</div>
    </div>
  </div>

  <div style="margin:4px 0;display:flex;align-items:center;gap:8px;justify-content:center">
    <div style="width:60px;text-align:right;font-size:10px;color:#f59e0b">技术约束<br>影响产品范围</div>
    <svg width="90" height="24" viewBox="0 0 90 24">
      <defs><marker id="rb1" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#f59e0b"/></marker></defs>
      <path d="M 80,12 Q 45,2 10,12" stroke="#f59e0b" stroke-width="1.5" fill="none" stroke-dasharray="4,3" marker-end="url(#rb1)"/>
      <text x="45" y="10" text-anchor="middle" font-size="9" fill="#f59e0b">退回 Step 1</text>
    </svg>
    <div style="width:60px"></div>
  </div>
  <div class="arrow"></div>

  <div class="phase-row">
    <div style="width:170px"></div>
    <div class="phase">
      <div class="phase-label">Step 3</div>
      <div class="phase-title">交互逻辑</div>
      <div class="phase-file">FLOWS.md</div>
      <div class="phase-desc">动作 · 反馈 · 四种状态 · 异常路径</div>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <div class="connector-h"></div>
      <div class="side-note-box">覆盖：加载 / 空 /<br>错误 / 成功 四态</div>
    </div>
  </div>

  <div style="margin:4px 0;display:flex;align-items:center;gap:8px;justify-content:center">
    <div style="width:60px;text-align:right;font-size:10px;color:#f59e0b">交互超出<br>技术边界</div>
    <svg width="90" height="24" viewBox="0 0 90 24">
      <defs><marker id="rb2" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#f59e0b"/></marker></defs>
      <path d="M 80,12 Q 45,2 10,12" stroke="#f59e0b" stroke-width="1.5" fill="none" stroke-dasharray="4,3" marker-end="url(#rb2)"/>
      <text x="45" y="10" text-anchor="middle" font-size="9" fill="#f59e0b">退回 Step 2</text>
    </svg>
    <div style="width:60px"></div>
  </div>
  <div class="arrow"></div>

  <div class="phase-row">
    <div style="width:170px"></div>
    <div class="phase">
      <div class="phase-label">Step 4</div>
      <div class="phase-title">前端交接包</div>
      <div class="phase-file">FRONTEND_HANDOFF.md</div>
      <div class="phase-desc">自包含规格 · 含角色声明</div>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <div class="connector-h"></div>
      <div class="side-note-box">前端 AI 只读<br>这一份即可开工</div>
    </div>
  </div>
  <div class="arrow"></div>

  <div class="phase-row">
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;width:170px">
      <div class="side-note-box" style="width:140px;text-align:right">专业前端 AI<br>（Cursor / v0 等）</div>
      <div class="connector-h" style="transform:rotate(180deg)"></div>
    </div>
    <div class="phase">
      <div class="phase-label">Step 5</div>
      <div class="phase-title">前端生成代码</div>
      <div class="phase-file">源码</div>
      <div class="phase-desc">严格按交接包实现 · 不自行扩展</div>
    </div>
    <div style="width:170px"></div>
  </div>
  <div class="arrow"></div>

  <div class="phase-row">
    <div style="width:170px"></div>
    <div class="phase">
      <div class="phase-label">Step 6</div>
      <div class="phase-title">项目记录</div>
      <div class="phase-file" style="display:block;margin-bottom:2px">STATUS.md</div>
      <div class="phase-file" style="display:block;margin-bottom:2px">CHANGELOG.md</div>
      <div class="phase-file">ERRORS.md</div>
      <div class="phase-desc">状态 · 版本 · 踩坑 · 下次接续</div>
    </div>
    <div style="width:170px"></div>
  </div>
  <div class="arrow"></div>

  <div class="phase-row">
    <div style="width:170px"></div>
    <div class="gate">
      <div class="gate-title">Step 7 · 验收闸门</div>
      <div class="gate-sub">bash check.sh · P0 验收标准</div>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
      <div class="connector-h"></div>
      <div class="side-note-box">通过 → 完成<br>不通过 → 修复<br>不靠 AI 自我报告</div>
    </div>
  </div>

  <div style="margin-top:6px;display:flex;justify-content:center">
    <svg width="220" height="30" viewBox="0 0 220 30">
      <defs><marker id="failarrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto"><path d="M0,0 L0,6 L6,3 z" fill="#6b7280"/></marker></defs>
      <path d="M 110,8 Q 110,22 60,22 Q 30,22 30,8" stroke="#9ca3af" stroke-width="1.5" fill="none" stroke-dasharray="4,3" marker-end="url(#failarrow)"/>
      <text x="110" y="20" text-anchor="middle" font-size="10" fill="#9ca3af">未通过 → 修复后重跑</text>
    </svg>
  </div>

  <div class="legend">
    <div class="legend-item">
      <div class="legend-dot" style="background:#2563eb;border-radius:3px"></div>
      主流程（线性推进）
    </div>
    <div class="legend-item">
      <svg width="18" height="10"><line x1="0" y1="5" x2="18" y2="5" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,3"/></svg>
      约束冲突 → 退回
    </div>
    <div class="legend-item">
      <svg width="18" height="10"><line x1="0" y1="5" x2="18" y2="5" stroke="#9ca3af" stroke-width="1.5" stroke-dasharray="4,3"/></svg>
      验收未通过 → 修复
    </div>
  </div>

</div>
</body>
</html>
```

---

## 【模块逐个介绍】3:30 - 10:00

---

### AGENTS.md — 框架的大脑

`AGENTS.md` 是整套框架的唯一默认入口。

它做三件事：

第一，维护一张**状态表**——当前在哪个步骤、PRD 完成了没有、代码写到哪里了、有没有报错记录。每次对话开始，AI 先看这张表，知道自己站在哪里。

第二，提供一张**文件路由表**——不同的任务场景，读哪些文件，不读哪些文件，写得清清楚楚。比如你在做 PRD，只读 `PRD.md`，其他文件一律不碰。你在修 bug，只读报错记录和相关源码，产品文档根本不用打开。

第三，定义**各阶段的角色**——PRD 阶段，AI 是资深产品经理，不是表格填写员；技术框架阶段，AI 是架构师，要为每个不可逆决策给出理由；验收阶段，AI 是 QA 工程师，用脚本说话，不用嘴说话。

这个设计解决了 AI 最常见的一个问题：**它不知道自己现在是谁、在做什么。** 给它一个角色，它的回答质量会显著提高。

---

### PRD.md — 产品的根基

PRD 是整套框架的地基。后面所有阶段的决策，都要回来对这份文档。

一份合格的 PRD 只需要回答四个问题：

- 这个产品一句话是什么？
- 核心用户是谁，他们的真实场景是什么？
- P0 做什么，P1 做什么，什么坚决不做？
- 什么叫完成？验收标准是什么？

这里有一个特别重要的原则：**在 AI 的协助下做 PRD，不是让 AI 替你想，而是让它逼你想清楚。** AI 扮演产品经理，每次最多问三个真正有价值的问题，不抛长问卷，不瞎猜业务背景。

PRD 确认之前，绝对不进入技术阶段。

---

### PROJECT_FRAME.md — 技术框架

技术框架文档解决的是"我们用什么造"的问题。

它覆盖的内容包括：技术栈选择和理由、目录结构、模块边界（每个模块负责什么、不负责什么）、数据模型、实现切片（从 M0 到 M3，每个切片独立可验收）。

这个文件有一个硬性规定：**所有不可逆的技术决策，必须写明理由，并且得到用户明确确认，才能往下走。** 你不能让 AI 悄悄帮你选了数据库、选了状态管理方案，然后两周后才发现这个选择走不通。

对于全栈项目，这个文件还需要在进入交互逻辑之前，把 API 设计方向锁定——是前端先用 mock，还是真实 API？前后端谁先动？

---

### FLOWS.md — 交互逻辑

FLOWS.md 是给人看的交互规格，也是后面生成前端交接包的原材料。

它不描述"界面长什么样"，它描述"用户做了什么，系统会怎么反应"。

每一个交互节点，必须覆盖四种状态：**加载中、空状态、错误态、成功态。** 这四种状态，是前端 AI 最容易遗漏的，也是用户体验最容易翻车的地方。

---

### FRONTEND_HANDOFF.md — 前端交接包

这是整套框架设计上最有意思的一个文件。

它的目标是：**把你的 AI 对话成果，打包成一份可以扔给另一个 AI 的自包含规格。**

为什么要这样做？因为不同的 AI 工具擅长不同的事情。Claude 擅长产品和架构思考，Cursor 或者 v0 擅长快速生成前端代码。你不应该让同一个 AI 又想需求又写代码——它会在两个角色之间漂移。

FRONTEND_HANDOFF.md 解决的就是这个问题。它包含了前端 AI 开工所需的一切：产品摘要、技术边界、页面模块、交互契约、状态要求、视觉要求、Mock 数据、禁止事项、验收标准。

文件开头有一段角色声明，明确告诉接收这份文件的 AI：**你是前端实现工程师，之前的所有决策你没参与，你只按这份规格来，不自行发挥。**

---

### STATUS.md / CHANGELOG.md / ERRORS.md — 记忆三件套

这三个文件解决的是同一个问题：**AI 没有长期记忆。**

每次对话结束，上下文就消失了。如果你没有结构化地把进展、版本、踩坑记录下来，下一次对话你就得重新解释一遍"我们上次做到哪了"。

- `STATUS.md` 记录"现在在哪"——当前版本、当前任务、卡点、下一步。
- `CHANGELOG.md` 记录"走过哪里"——每个完成的版本。
- `ERRORS.md` 记录"踩过什么坑"——报错复现、根因、处理方式、预防规则。

特别是 `ERRORS.md`，在接续已有项目的时候，`AGENTS.md` 会提示 AI 主动读取它。**避免同一个坑踩两次。**

---

### GATES.md + check.sh — 验收闸门

最后一关。

很多人用 AI 写完代码，问它"完成了吗"，它说"完成了"。然后你一跑，全是问题。

**你不能信任 AI 的自我报告。**

`GATES.md` 定义什么叫完成，`check.sh` 是可执行的检查脚本。只有 `bash check.sh` 通过、P0 验收标准满足，才允许声称完成。这是硬性规定，没有例外。

---

## 【总结】10:00 - 11:00

好，我们把整套框架过了一遍。

它的核心逻辑就是三件事：

**第一，上下文最小化。** 每次只读必要的文件，不把整个项目塞进 AI 的脑子里。

**第二，决策串行化。** 每个阶段有明确的完成条件，不确认就不往下走，冲突就退回去重新确认。

**第三，记忆外部化。** 状态、版本、报错分文件记录，让 AI 的记忆活在文件里，不活在对话里。

这套框架是开源的，文件结构我都已经准备好了，你可以直接拿去用。链接在视频描述里。

如果你觉得有用，点个关注，下期我会手把手带你用这套框架从零搭一个真实项目。
