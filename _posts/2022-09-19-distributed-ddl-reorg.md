---
layout: redirect
title: Proposal for Supporting Distributed DDL Reorg in TiDB
redirect_to: https://github.com/pingcap/tidb/blob/master/docs/design/2022-09-19-distributed-ddl-reorg.md
---

This is distributed processing of design in the DDL reorg phase. The current design is based on the main logic that only the DDL owner can handle DDL jobs. However, for jobs in the reorg phase, it is expected that all TiDBs can claim subtasks in the reorg phase based on resource usage.
