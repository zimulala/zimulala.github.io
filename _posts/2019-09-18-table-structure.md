---
layout: single
title: 表结构设计最佳实践
category: TiDB
---

本文基于 TiDB 的实现机制，介绍表结构在设计时的注意事项以及建议。  
读者在阅读本文之前，知道 TiDB [整体架构](https://docs.pingcap.com/zh/tidb/stable/tidb-architecture) ，了解 TiDB 原理的三篇文章（[讲存储](https://pingcap.com/blog-cn/tidb-internal-1)，[说计算](https://pingcap.com/blog-cn/tidb-internal-2)，[谈调度](https://pingcap.com/blog-cn/tidb-internal-3)）。

# 表

## 存储格式

对于一个 Table 来说，需要存储的数据包括表的元信息、表的行数据和索引数据三部分。

### 表的元信息

每个表会将一些基础信息以有一个 TableID 在整个集群内唯一，IndexID/RowID 在表内唯一，这些 ID 都是 int64 类型。

### 表的行数据

TiDB 对每个表分配一个 TableID，每一个索引都会分配一个 IndexID，每一行分配一个 RowID（如果表有整数型的 Primary Key，那么会用 Primary Key 的值当做 RowID）。

每行数据按照如下规则进行编码成 Key-Value pair：

```go
 Key: tablePrefix{tableID}_recordPrefixSep{rowID}Value: [colID1, colVal1, colID2, colVal2 ... colIDn, colValn]
```

其中 Key 的 tablePrefix/recordPrefixSep 都是特定的字符串常量，用于在 KV 空间内区分其他数据。

### 索引数据

对于 Index 数据，还需要考虑 Unique Index 和非 Unique Index 两种情况，具体会按照如下规则编码成 Key-Value pair：

* Unique Index 编码方式

```go
Key: tablePrefix{tableID}_indexPrefixSep{indexID}_indexedColumnsValueValue: RowID
```

* 非 Unique Index，不能通过 Unique Index 的编码方式构造出唯一的 Key。 那么可能有多行数据的 Value 是一样的，所以对于非 Unique Index 的编码做了一点调整：

```go
Key: tablePrefix{tableID}_indexPrefixSep{indexID}_indexedColumnsValue_rowIDValue: null
```

上述编码规则中的 Key 里面的各种 xxPrefix 都是字符串常量，作用都是区分命名空间，以免不同类型的数据之间相互冲突，定义如下：

```go
var(tablePrefix     = []byte{'t'}recordPrefixSep = []byte("_r")indexPrefixSep  = []byte("_i"))
```

## 列

存储超宽表是比较不合适的，特别是一行的列非常多，同时不是太稀疏，一个经验是最好单行的总数据大小不要超过 64K，越小越好。大的数据最好拆到多张表中。

## 索引

TiDB 支持完整主键索引和二级索引，并且是全局索引，很多查询可以通过索引来优化。很多 MySQL 上的经验在 TiDB 这里依然适用，不过 TiDB 还有一些自己的特点。一些注意事项如下：

* **不是索引建的越多越好**。二级索引能加速查询，但是要注意新增一个索引是有副作用的。  
  * 每增加一个索引，在插入一条数据的时候，就要新增一个 Key-Value，所以索引越多，写入越慢，并且空间占用越大。  
  * 另外过多的索引也会影响优化器运行时间，并且不合适的索引会误导优化器。  
* **对哪些列建索引比较合适**。我们需要根据具体的业务特点创建合适的索引。原则上我们需要对查询中需要用到的列创建索引，目的是提高性能。下面几种情况适合创建索引：  
  * 区分度比较大的列，通过索引能显著地减少过滤后的行数。  
  * 有多个查询条件时，可以选择组合索引，注意需要把等值条件的列放在组合索引的前面。这里举一个例子，假设常用的查询是 select \* from t where c1 \= 10 and c2 \= 100 and c3 \> 10, 那么可以考虑建立组合索引 Index cidx (c1, c2, c3)，这样可以用查询条件构造出一个索引前缀进行 Scan。  
* **减少单调递增索引。**

### 主键索引

对于整型的主键索引如之前存储格式章节描述，我们会将其值当做 RowID 存储。那么此类索引可以减少存储空间。但是此类索引数据如果是单调递增的话就不能使用 split table/ index 的语句来分裂 region，从而分散热点数据。

### 复合索引

与其他数据库一样，设计复合索引的一般原则是尽可能的把使用频率比较高的字段放在前面，经常被点查使用的列排在前面，将经常进行范围查询的列排在后面。在当前版本（v3.0 及以下的全部版本）使用中需要特别注意，复合索引中前一列的范围查询会中止后续索引列的使用。  
例子：

```sql
select a,b,c from tableName where a<predicate>'<value1>' and b<predicate>'<value2>' and c<predicate>'<value3>'; |
```

如果 a 条件的谓词（语句中的 predicate）是 \= 或 in，那么在 b 的查询条件上就可以利用到组合索引 (a,b,c) 。例：select a,b,c from tableName where a=1 and b\<5 and c=’abc’。  
同样的，如果 a 条件和 b 条件的谓词都是 \= 或 in，那么在 c 上的查询就可以利用到组合索引 (a,b,c) 。例：select a,b,c from tableName where a in(1,2,3) and b=5 and c=’abc’。  
如果 a 条件的谓词不是 \= 也不是 in，那么 b 上的查询就无法利用到组合索引 (a,b,c) 。此时 b 条件将在 a 条件筛选后的数据中进行无索引的数据扫描。例：select a,b,c from tableName where a\>1 and b\<5 and c=’abc’。

## 自增 ID

自增 ID 在 TiDB 的实现情况可以参考[自增 ID 文档](https://docs.pingcap.com/zh/tidb/dev/mysql-compatibility/#%E8%87%AA%E5%A2%9E-id)。  
对于分布式数据库来说，带自增 ID 的表，随着插入的压力增大，会形成 Region 热点，且这个热点并没有办法分散到多台机器。因此，如无必要不推荐使用自增 ID。那么对于通过依赖自增 ID 来作为 PRIMARY KEY 的情况，建议使用随机的 UUID 或者对单调递增的 ID 进行 bit-reverse （位反转）来替代自增 ID 列的使用。

### 最佳实践

自增 ID 列的类型必须为整型，在几种整型类型中，我们建议使用 bigint。这是由于即使在单机数据库中也屡见 int 类型的自增 ID 被耗光的情况，而 TiDB 被用于处理比单机数据大得多的数据量。此外自增 ID 一般不需要存储负值，为列增加 unsigned 属性可以扩充一倍的 id 存储容量。int 无符号的范围是 0 到 4294967295，bigint 无符号的范围是 0 到 18446744073709551615  
例子如下：

```sql
`aut_inc_id` bigint unsigned not null unique key auto\_increment comment '自增 ID'
```

## 其它 Options

### shard\_row\_id\_bits

可以通过 TiDB 内部机制 shard\_row\_id\_bits 来实现热点的分散。这个具体使用可以参考：[TiDB 高并发写入常见热点问题及规避方法](https://cn.pingcap.com/blog/tidb-in-high-concurrency-scenarios)。

# 分区表

目前 TiDB 里面只实现了 Range 分区和 Hash 分区。通过合理的涉及分区规则，可以进一步避免写入热点问题，加速删除数据和查询。