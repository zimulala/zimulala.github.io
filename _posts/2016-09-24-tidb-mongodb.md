---
layout: single
title: Go 和 TiDB 创造另一个 mongodb
category: golang
---

本 PPT 介绍了如何利用 Go 语言 和 TiDB，构建出一个类似于 MongoDB 的简单功能系统。

---


# About me


* 目前在 PingCAP 就职
  * 15 年中加入 PingCAP
  * 目前负责 TiDB 方面的开发和 review
* 之前在京东就职
  * 12 年末入职，学习 go 并且开始做云推送项目
  * 13 年末开始做存储方面的工作，云存储和弹性块存储项目
* 联系方式
  * 微博：@紫沐夏\_go
  * Email: lixia@pingcap\.com

---


# Agenda

mongodb introduction

gonzo with memory engine

gonzo with TiKV engine

TiDB and TiKV

Transaction

Q & A

---


# mongodb introduction

![图1](/images/tidb-mongodb/mongodb introduction.png)

---


# mongodb introduction

* docment
  * 文档是一个键值\(key\-value\)对\(即BSON\)。MongoDB 的文档不需要设置相同的字段，并且相同的字段不需要相同的数据类型。
 
![图2](/images/tidb-mongodb/mongodb introduction-1.png)

---


# gonzo with memory engine

一个 mongo 的内存服务

解析客户端的协议，然后将操作存到内存，最后将操作结果返回给客户端

实现简单的增删改查

---

# gonzo with memory engine

演示

---


# gonzo with memory engine


insert 实现

![图3](/images/tidb-mongodb/insert.png)

---


# gonzo with memory engine

find 实现

![图4](/images/tidb-mongodb/find.png)

---

# gonzo with TiKV engine

* 目前只实现了 insert 和 find 的接口
* 用最简单的方式接入
  * 与 TiDB 一样分成了 schema 信息和 table 数据存储
  * 用了 TiDB 的事物接口 RunInNewTxn
  * 都直接从 TiKV 获取数据，可以用 TiDB 自带

* TiDB 的引擎是可插拔的，其他应用也可以直接用 TiKV

---

# gonzo with TiKV engine

insert 实现
![图5](/images/tidb-mongodb/insert-1.png)

---


# gonzo with TiKV engine

find 部分实现
![图6](/images/tidb-mongodb/find-1.png)

---


# gonzo with TiKV engine

演示

---


# mongodb

* <span style="color:#215d77"></span> 优：
  * 非结构化存储，schema\-less 灵活，查询快速
  * 高可用（Replica Set）、可扩展性、容错能力等属性
* <span style="color:#215d77"></span> 劣：
  * 很多做不到ACID特性，不支持事务
  * 不支持SQL
  * Cluster 同步带宽占用过多的问题

---


# TiDB and TiKV

![图7](/images/tidb-mongodb/tidb-tikv.png)

---


# TiDB

* 有如下特性:
* MySQL 协议
  * 用户从 MySQL 的相关解决方案迁移过来时几乎没迁移成本。
* 异步 schema 变更
  * 参考 Google 动态变更 schema 的论文
* 支持 hash join
  * 小表放到内存，等值 key 建立哈希表
  * 大表是用 goroutine 分批取值，匹配哈希表
  * 之后会支持 merge sort join 等常用算法

![图8](/images/tidb-mongodb/tidb.png)

---

# TiDB

* 有如下特性:
* 分布式事务
  * 2PC（二阶段提交），参考 Google percolator的论文
  * 隔离级别 （SI ＋ 乐观锁）
* 水平扩容/缩容
  * raft 协议 ＋ PlacementDriver
* 容错

---


# TiKV

![图9](/images/tidb-mongodb/tikv.png)

---


# Transaction

* 在 kv 上支持事务
  * k1 和 k2 两人
  * k1 在银行中存 10 元
  * k2 在银行中存 20 元
  * 现 k1 给 k2 账户上转 1 元

![图10](/images/tidb-mongodb/txn.png)
---


# Transaction

* 在 kv 上支持事务
* 假设 step 4 失败
  * k1 给 k3 转 10 元，当操作进行到 step 2 时
  * k2 查询自己账户余额

![图11](/images/tidb-mongodb/txn-1.png)

---


# Transaction

* 目前 TiKV 事务支持的实现
* 3 column families （存于 rocksdb）
  * __lock__ :  未提交的事务会填写 primary key 的信息
  * __write__ : 存储 commit 时间戳
  * __data__ : 存储数据

---


# TiDB

<span style="color:#000000">演示</span>

---


# Feelings

* 关于代码风格
  * 对于原先的我更多的是代码命名方面的问题，一步一步的修改
* 在这个团队里，让我的感受是没有挺好，你可以更好
* 分享个小故事
  * 有时候你也想偷个小懒，某个问题改不改差一点点，于是乎就没改，但是还是会被眼尖的同事发现，然后默默地改过来，是不是有点小忧（搞）伤（笑）
  * 想想下次还是自己改了吧，省的 PR 上多了一两个 comments， 多不好看呀，哈哈。

---


# Q & A

__项目地址__

__TiDB: __  _[http://github\.com/pingcap/tidb](http://github.com/pingcap/tidb)_  __    	（4700\+ stars）__

__TiKV: __  _[https://github\.com/pingcap/tikv](https://github.com/pingcap/tikv)_  __     	（1000\+ stars）__

