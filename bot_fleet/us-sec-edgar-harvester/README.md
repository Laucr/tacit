# 🧩 US SEC EDGAR Harvester

**简体中文** | [English](README.en.md)

> 一句话定位：把美国 SEC EDGAR 的公开申报文件（8-K / Form 4 / 13D-13G / 13F / S-1）抓取并结构化成一份**去重、标注来源、带时间线**的数据集——只做讯息收集，不做分析、不做推荐。

![type](https://img.shields.io/badge/type-skill-blue)
![category](https://img.shields.io/badge/category-data--api-blue)
![license](https://img.shields.io/badge/license-GPLv3-blue)

## 📖 这是什么

`us-sec-edgar-harvester` 是一个**纯讯息收集（information collection）**技能。给定一个美股标的、一位内部人（Form 4 申报人）或一家机构（13F 申报人），它把 SEC EDGAR 的**一手公开申报**抓下来，解析出关键结构化字段，按 accession number 去重、处理 `/A` 修订件的替代关系，最终产出一份**带来源、带日期的时间线 + 一张结构化数据表**。

它只读 **SEC EDGAR 公开接口**：全文检索（efts.sec.gov）、submissions API（data.sec.gov）、ticker→CIK 映射，以及 Archives 下的申报索引与文档。技能本身只提供接口清单、字段映射与规则，真正的 HTTP 请求交给运行时的联网/抓取能力执行。

**与姊妹仓库的区别**：`hk-us-insider-radar`、`hk-us-holder-concentration` 走的是 **Pandadata 供应商数据源**（归一化、跨市场、需密钥）；本技能走的是 **SEC 一手公开源**，保留 accession 级别的可追溯出处。需要可引用的原始 EDGAR 申报时用本技能；需要供应商归一化数据时用那两个 Pandadata 技能。

**输入**：美股代码 / 公司名 / 内部人 / 机构名 + 申报类型 + 时间窗。
**产出**：`filings_dataset.csv`（每条申报或每笔 Form 4 交易一行）、`filing_timeline.md`（带 accession 的时间线）、以及一段只讲事实的覆盖度小结。

## 🚀 快速开始

```bash
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
├── SKILL.md
├── README.md
├── README.en.md
├── LICENSE
├── agents/
│   └── openai.yaml
├── references/
│   ├── edgar-sources.md
│   ├── methodology.md
│   └── source_boundary.md
└── scripts/
    └── validate_report.py
```

## 🖼️ 产出说明

本仓库默认不提交生成产物。`filings_dataset.csv`、`filing_timeline.md` 和覆盖度小结随运行生成并保存在本地；数据来自 SEC EDGAR 公开申报。

## 🔌 运行时兼容

以 `SKILL.md` 为统一入口，可在 Claude Code、Codex、Cursor、Hermes、OpenClaw 等运行时加载。

## 🌐 数据来源与依赖

- `https://efts.sec.gov/LATEST/search-index`
- `https://data.sec.gov/submissions/CIK##########.json`
- `https://www.sec.gov/files/company_tickers.json`
- `https://www.sec.gov/Archives/edgar/data/<cik>/<accession>/`

全部为公开、无需密钥的 SEC 接口；依赖运行时联网能力。不捆绑 API key。

## ⚠️ 限制与风险边界

- 只做讯息收集，不打分、不排名、不估值、不预测、不推荐。
- 只读公开 SEC 数据；使用描述性通用 User-Agent。
- 遵守 SEC 限速；遇 403/429 退避并报告部分覆盖。
- 区分申报/受理日与事件/报告期日；`/A` 修订件保留替代链。
- Form 4 代码原样记录；13F 天然滞后且仅含美股多头。

## 🧾 免责声明

本仓库仅整理 SEC EDGAR 公开申报的收集与结构化方法，非官方、不隶属 SEC 或任何被披露主体，不构成任何投资建议。

## 📜 License

GPLv3. See [LICENSE](LICENSE).

## 🧑‍🔧 维护者

Created or maintained by `abgyjaguo`.
