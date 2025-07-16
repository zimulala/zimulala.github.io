---
layout: redirect
title: TiDB 源码阅读系列文章（八）基于代价的优化
redirect_to: https://cn.pingcap.com/blog/tidb-source-code-reading-8
---

本文是 TiDB 源码阅读系列文章的第八篇。内文会先简单介绍制定查询计划以及优化的过程，然后用较大篇幅详述在得到逻辑计划后，如何基于统计信息和不同的属性选择等生成各种不同代价的物理计划，通过比较物理计划的代价，最后选择一个代价最小的物理计划，即 Cost-Based Optimization（CBO）的过程。
