# 🧩 US SEC EDGAR Harvester

**简体中文** | [English](README.en.md)

> 一句话定位：把美国 SEC EDGAR 的公开申报文件（8-K / Form 4 / 13D-13G / 13F / S-1）抓取并结构化成一份**去重、标注来源、带时间线**的数据集——只做讯息收集，不做分析、不做推荐。

![type](https://img.shields.io/badge/type-skill-blue)
![category](https://img.shields.io/badge/category-data--api-blue)
![license](https://img.shields.io/badge/license-GPLv3-blue)

## 📖 这是什么

`us-sec-edgar-harvester` 是一个**纯讯息收集（information collection）**技能。给定一个美股标的、
一位内部人（Form 4 申报人）或一家机构（13F 申报人），它把 SEC EDGAR 的**一手公开申报**抓下来，
解析出关键结构化字段，按 accession number 去重、处理 `/A` 修订件的替代关系，最终产出一份
**带来源、带日期的时间线 + 一张结构化数据表**。

它只读 **SEC EDGAR 公开接口**：全文检索（efts.sec.gov）、submissions API（data.sec.gov）、
ticker→CIK 映射，以及 Archives 下的申报索引与文档。技能本身只提供接口清单、字段映射与规则，
真正的 HTTP 请求交给运行时的联网/抓取能力执行。

**与姊妹仓库的区别**：`hk-us-insider-radar`、`hk-us-holder-concentration` 走的是 **Pandadata 供应商
数据源**（归一化、跨市场、需密钥）；本技能走的是 **SEC 一手公开源**，保留 accession 级别的可追溯出处。
需要可引用的原始 EDGAR 申报时用本技能；需要供应商归一化数据时用那两个 Pandadata 技能。

**输入**：美股代码 / 公司名 / 内部人 / 机构名 + 申报类型 + 时间窗。
**产出**：`filings_dataset.csv`（每条申报或每笔 Form 4 交易一行）、`filing_timeline.md`（带 accession 的
时间线）、以及一段只讲事实的覆盖度小结。

## 🚀 快速开始

```bash
# 复制到 Claude Code 技能目录（其它运行时见「运行时兼容」）
cp -r skill-us-sec-edgar-harvester ~/.claude/skills/us-sec-edgar-harvester
```

触发示例 prompt：

```text
帮我抓一下 AAPL 最近 90 天的 8-K 和 Form 4，做成带来源的时间线
收集 Tesla 内部人（Form 4）过去一年的 P/S 开市买卖交易，去重列成表
把某基金最新一期 13F 持仓从 EDGAR 拉下来并标注报告期
```

产出后可自检：

```bash
python scripts/validate_report.py path/to/filing_timeline.md
```

## 📦 目录结构

```text
skill-us-sec-edgar-harvester/
├── SKILL.md                       # 运行时入口：编号工作流 + 输出契约 + 边界
├── README.md                      # 中文优先说明（本文件）
├── README.en.md                   # English
├── LICENSE                        # GPLv3
├── agents/
│   └── openai.yaml                # OpenAI / Codex 适配（cursor-rule.mdc、portable-loader.md 由 workspace sync 生成）
├── references/
│   ├── edgar-sources.md           # EDGAR 接口、URL 形态、请求头与限速规则
│   ├── methodology.md             # 逐表字段映射、交易代码、去重/替代、日期语义、坑
│   └── source_boundary.md         # 数据边界：只读公开 EDGAR
└── scripts/
    └── validate_report.py         # 报告自检（章节 + 来源/日期出处 + 免责，坏报告非零退出）
```

## 🖼️ 产出说明

本仓库**默认不提交生成产物**（申报数据集与时间线随运行生成，保存在本地）。产物形态如下：

| 产物 | 用途 | 如何生成 | 数据基础 | 公开安全 |
| --- | --- | --- | --- | --- |
| `filings_dataset.csv` | 供脚本/人复用的结构化表，每行带 accession 与 source_url | 按 SKILL.md 工作流运行 | SEC EDGAR 公开申报 | 均为公开数据；不含密钥 |
| `filing_timeline.md` | 供人阅读的带来源、带日期时间线 | 同上 | 同上 | 同上 |
| 覆盖度小结 | 说明主体、CIK、类型、窗口、条数、缺口 | 同上 | 同上 | 同上 |

## 🔌 运行时兼容

以 `SKILL.md` 为统一入口，可在 **Claude Code、Codex、Cursor、Hermes、OpenClaw** 等运行时加载；
`agents/` 下提供各运行时适配文件（`cursor-rule.mdc`、`portable-loader.md` 由 workspace 的技能 sync
统一生成）。

## 🌐 数据来源与依赖

- **EDGAR 全文检索**：`https://efts.sec.gov/LATEST/search-index`
- **EDGAR submissions API**：`https://data.sec.gov/submissions/CIK##########.json`
- **ticker→CIK 映射**：`https://www.sec.gov/files/company_tickers.json`
- **申报索引与文档**：`https://www.sec.gov/Archives/edgar/data/<cik>/<accession>/`

全部为公开、无需密钥的 SEC 接口。依赖运行时的联网/抓取能力发起请求；不捆绑任何 API key。
详见 `references/edgar-sources.md` 与 `references/methodology.md`。

## ⚠️ 限制与风险边界

- **只做讯息收集**：抓取并结构化公开事实，**不打分、不排名、不估值、不预测、不推荐**。
- **只读公开 SEC 数据**：不含密钥；必须按 SEC 公平使用政策发送**描述性通用 User-Agent**——不写死任何
  密钥，也不填他人私人联系方式（除非用户主动提供自己的）。
- **限速与降级**：遵守 SEC 限速（约 10 次/秒上限，实操更保守）；遇 403/429 退避并**如实报告部分覆盖**，
  不静默丢数据。
- **日期语义**：申报/受理日 ≠ 事件/报告期日；每行都标注用的是哪种日期。
- **修订件**：`/A` 修订件替代原件，两者都保留并标注替代链，不覆盖原件。
- **Form 4 代码**：`P/S/A/M/F/G/...` 原样记录，不把授予/代扣简化成「买入」。
- **13F 滞后**：报告期后最多 45 天才申报，只含美股多头，天然滞后。
- **需人工确认**：任何对外写操作（发送、发布、下单）都需要用户显式触发；本技能不做这些。

## 🧾 免责声明

本仓库仅整理 SEC EDGAR 公开申报的收集与结构化方法，非官方、不隶属 SEC 或任何被披露主体，
不验证任何收益声明，**不构成任何投资建议**。

## 🧑‍🔧 维护者

Created or maintained by `abgyjaguo`.

## 📜 License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE).

## 🐼 PandaAI / QUANTSKILLS 社群

<div align="center">
  <img src="https://raw.githubusercontent.com/quantskills/.github/main/profile/assets/pandaai-community-qr.jpg" alt="PandaAI 社群二维码" width="220">
  <br>
  <sub>扫码加入 PandaAI 社群，交流 QUANTSKILLS 技能、Agent 工作流与量化研究实践。</sub>
</div>
