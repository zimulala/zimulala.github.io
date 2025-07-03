---
layout: single 
title: Golang 中的 OpenTelemetry 快速入门
category: golang
---

本文将带您快速上手在 Golang 中使用 OpenTelemetry（OTel）。我们将从一个简单的 Golang 应用程序出发，学习如何采集并在控制台输出 trace、log 和 metrics 数据。接着，将介绍如何将追踪信息上报至 OTel Collector、Jaeger 和 Prometheus，并演示如何通过这些工具查看和分析观测数据。

## 创建并启动需要添加观测的服务

以下示例使用基本的 net/http 应用程序。

### 创建并启动 HTTP 服务器

在同一文件夹中，创建一个名为 main.go 的文件并将以下代码添加到该文件中：

```go
package main

import (
	"log"
	"net/http"
)

func main() {
	http.HandleFunc("/rolldice", rolldice)

	log.Fatal(http.ListenAndServe(":8080", nil))
}
```

创建另一个名为 rolldice.go 的文件，并将以下代码添加到该文件中：

```go
package main

import (
	"io"
	"log"
	"math/rand"
	"net/http"
	"strconv"
)

func rolldice(w http.ResponseWriter, r *http.Request) {
	roll := 1 + rand.Intn(6)

	resp := strconv.Itoa(roll) + "\n"
	if _, err := io.WriteString(w, resp); err != nil {
		log.Printf("Write failed: %v\n", err)
	}
}
```

使用以下命令构建并运行应用程序：

```go
go run .
```

在 Web 浏览器中打开 http://localhost:10081/rolldice 以确保其正常工作。

### 增加 OpenTelemetry 注入

现在我们将展示如何将OpenTelemetry注入添加到示例应用程序中。如果您正在使用自己的应用程序，可以跟随操作，只需注意您的代码可能会略有不同。

#### 添加依赖项

```shell
go get "go.opentelemetry.io/otel" \
"go.opentelemetry.io/otel/exporters/stdout/stdoutmetric" \
"go.opentelemetry.io/otel/exporters/stdout/stdouttrace" \
"go.opentelemetry.io/otel/exporters/stdout/stdoutlog" \
"go.opentelemetry.io/otel/sdk/log" \
"go.opentelemetry.io/otel/log/global" \
"go.opentelemetry.io/otel/propagation" \
"go.opentelemetry.io/otel/sdk/metric" \
"go.opentelemetry.io/otel/sdk/resource" \
"go.opentelemetry.io/otel/sdk/trace" \
"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"\
"go.opentelemetry.io/contrib/bridges/otelslog"
```

这将安装 OpenTelemetry SDK 组件和针对 net/http 的自动监测功能。如果你需要对其他用于网络请求的库进行监测，你可能需要安装相应的库监测工具。更多关于库的信息，请参见相关文档。

#### 初始化 OpenTelemetry SDK

首先，我们将初始化OpenTelemetry SDK。这对于任何导出遥测数据的应用程序都是必需的。
创建一个名为<font style="color:rgb(51, 51, 51);background-color:rgb(247, 249, 253);">otel.go</font>的文件，并在里面添加 OpenTelemetry SDK 的引导代码：

```go
package main

import (
	"context"
	"errors"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/stdout/stdoutlog"
	"go.opentelemetry.io/otel/exporters/stdout/stdoutmetric"
	"go.opentelemetry.io/otel/exporters/stdout/stdouttrace"
	"go.opentelemetry.io/otel/log/global"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/sdk/log"
	"go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/trace"
)

// setupOTelSDK bootstraps the OpenTelemetry pipeline.
// If it does not return an error, make sure to call shutdown for proper cleanup.
func setupOTelSDK(ctx context.Context) (shutdown func(context.Context) error, err error) {
	var shutdownFuncs []func(context.Context) error

	// shutdown calls cleanup functions registered via shutdownFuncs.
	// The errors from the calls are joined.
	// Each registered cleanup will be invoked once.
	shutdown = func(ctx context.Context) error {
		var err error
		for _, fn := range shutdownFuncs {
			err = errors.Join(err, fn(ctx))
		}
		shutdownFuncs = nil
		return err
	}

	// handleErr calls shutdown for cleanup and makes sure that all errors are returned.
	handleErr := func(inErr error) {
		err = errors.Join(inErr, shutdown(ctx))
	}

	// Set up propagator.
	prop := newPropagator()
	otel.SetTextMapPropagator(prop)

	// Set up trace provider.
	tracerProvider, err := newTraceProvider()
	if err != nil {
		handleErr(err)
		return
	}
	shutdownFuncs = append(shutdownFuncs, tracerProvider.Shutdown)
	otel.SetTracerProvider(tracerProvider)

	// Set up meter provider.
	meterProvider, err := newMeterProvider()
	if err != nil {
		handleErr(err)
		return
	}
	shutdownFuncs = append(shutdownFuncs, meterProvider.Shutdown)
	otel.SetMeterProvider(meterProvider)

	// Set up logger provider.
	loggerProvider, err := newLoggerProvider()
	if err != nil {
		handleErr(err)
		return
	}
	shutdownFuncs = append(shutdownFuncs, loggerProvider.Shutdown)
	global.SetLoggerProvider(loggerProvider)

	return
}

func newPropagator() propagation.TextMapPropagator {
	return propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	)
}

func newTraceProvider() (*trace.TracerProvider, error) {
	traceExporter, err := stdouttrace.New(
		stdouttrace.WithPrettyPrint())
	if err != nil {
		return nil, err
	}

	traceProvider := trace.NewTracerProvider(
		trace.WithBatcher(traceExporter,
			// Default is 5s. Set to 1s for demonstrative purposes.
			trace.WithBatchTimeout(time.Second)),
	)
	return traceProvider, nil
}

func newMeterProvider() (*metric.MeterProvider, error) {
	metricExporter, err := stdoutmetric.New()
	if err != nil {
		return nil, err
	}

	meterProvider := metric.NewMeterProvider(
		metric.WithReader(metric.NewPeriodicReader(metricExporter,
			// Default is 1m. Set to 3s for demonstrative purposes.
			metric.WithInterval(3*time.Second))),
	)
	return meterProvider, nil
}

func newLoggerProvider() (*log.LoggerProvider, error) {
	logExporter, err := stdoutlog.New()
	if err != nil {
		return nil, err
	}

	loggerProvider := log.NewLoggerProvider(
		log.WithProcessor(log.NewBatchProcessor(logExporter)),
	)
	return loggerProvider, nil
}
```

如果你只使用追踪（Tracing）或度量（Metrics），你可以省略对应的TracerProvider或MeterProvider初始化代码。

#### 对 HTTP Server 进行注入

现在我们已经初始化了 OpenTelemetry SDK，接下来可以对HTTP服务器进行监控（instrument）了。
请修改 main.go 文件，以包含以下代码：这将设置 OpenTelemetry SDK，并使用 otelhttp 库来对 HTTP 服务器进行监控。

```go
package main

import (
	"context"
	"errors"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"time"

	"go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp"
)

func main() {
	if err := run(); err != nil {
		log.Fatalln(err)
	}
}

func run() (err error) {
	// Handle SIGINT (CTRL+C) gracefully.
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()

	// Set up OpenTelemetry.
	otelShutdown, err := setupOTelSDK(ctx)
	if err != nil {
		return
	}
	// Handle shutdown properly so nothing leaks.
	defer func() {
		err = errors.Join(err, otelShutdown(context.Background()))
	}()

	// Start HTTP server.
	srv := &http.Server{
		Addr:         ":8080",
		BaseContext:  func(_ net.Listener) context.Context { return ctx },
		ReadTimeout:  time.Second,
		WriteTimeout: 10 * time.Second,
		Handler:      newHTTPHandler(),
	}
	srvErr := make(chan error, 1)
	go func() {
		srvErr <- srv.ListenAndServe()
	}()

	// Wait for interruption.
	select {
	case err = <-srvErr:
		// Error when starting HTTP server.
		return
	case <-ctx.Done():
		// Wait for first CTRL+C.
		// Stop receiving signal notifications as soon as possible.
		stop()
	}

	// When Shutdown is called, ListenAndServe immediately returns ErrServerClosed.
	err = srv.Shutdown(context.Background())
	return
}

func newHTTPHandler() http.Handler {
	mux := http.NewServeMux()

	// handleFunc is a replacement for mux.HandleFunc
	// which enriches the handler's HTTP instrumentation with the pattern as the http.route.
	handleFunc := func(pattern string, handlerFunc func(http.ResponseWriter, *http.Request)) {
		// Configure the "http.route" for the HTTP instrumentation.
		handler := otelhttp.WithRouteTag(pattern, http.HandlerFunc(handlerFunc))
		mux.Handle(pattern, handler)
	}

	// Register handlers.
	handleFunc("/rolldice/", rolldice)
	handleFunc("/rolldice/{player}", rolldice)

	// Add HTTP instrumentation for the whole server.
	handler := otelhttp.NewHandler(mux, "/")
	return handler
}
```

#### 增加第三方注入

注入库在系统的边缘处捕获遥测数据，例如入站和出站HTTP请求，但它们不会捕获应用程序内部的情况。为此，您需要编写一些自定义的手动注入代码。
使用 OpenTelemetry API 修改 rolldice.go 以包含自定义注入：

```go
package main

import (
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"strconv"

	"go.opentelemetry.io/contrib/bridges/otelslog"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
)

const name = "go.opentelemetry.io/otel/example/dice"

var (
	tracer = otel.Tracer(name)
	meter  = otel.Meter(name)
	logger = otelslog.NewLogger(name)
	rollCnt metric.Int64Counter
)

func init() {
	var err error
	rollCnt, err = meter.Int64Counter("dice.rolls",
		metric.WithDescription("The number of rolls by roll value"),
		metric.WithUnit("{roll}"))
	if err != nil {
		panic(err)
	}
}

func rolldice(w http.ResponseWriter, r *http.Request) {
	ctx, span := tracer.Start(r.Context(), "roll")
	defer span.End()

	roll := 1 + rand.Intn(6)

	var msg string
	if player := r.PathValue("player"); player != "" {
		msg = fmt.Sprintf("%s is rolling the dice", player)
	} else {
		msg = "Anonymous player is rolling the dice"
	}
	logger.InfoContext(ctx, msg, "result", roll)

	rollValueAttr := attribute.Int("roll.value", roll)
	span.SetAttributes(rollValueAttr)
	rollCnt.Add(ctx, 1, metric.WithAttributes(rollValueAttr))

	resp := strconv.Itoa(roll) + "\n"
	if _, err := io.WriteString(w, resp); err != nil {
		log.Printf("Write failed: %v\n", err)
	}
}
```

请注意，如果您仅使用跟踪或度量，可以省略用于注入另一种遥测类型对应的代码。
运行应用
通过以下命令编译并运行这个应用：

```shell
go mod tidy
export OTEL_RESOURCE_ATTRIBUTES="service.name=dice,service.version=0.1.0"
go run .
```

在您的网络浏览器中打开 http://localhost:10081/rolldice/Alice。当您向服务器发送请求时，您将在控制台看到两个跨度（span）记录。由监控库生成的跨度跟踪了对/rolldice/{player} 路由的请求生命周期。另一个称为“roll”的跨度是手动创建的，并且它是前一个提到的跨度的子级。

查看 demo 输出
```json
{
  "Name": "roll",
  "SpanContext": {
    "TraceID": "34a760f24420c2d0c1a7ad7d6a8ef814",
    "SpanID": "5a09abab43d9faf6",
    "TraceFlags": "01",
    "TraceState": "",
    "Remote": false
  },
  "Parent": {
    "TraceID": "34a760f24420c2d0c1a7ad7d6a8ef814",
    "SpanID": "9c39e2a2f661e792",
    "TraceFlags": "01",
    "TraceState": "",
    "Remote": false
  },
  "SpanKind": 1,
  "StartTime": "2024-11-29T11:50:39.809163+08:00",
  "EndTime": "2024-11-29T11:50:39.809376042+08:00",
  "Attributes": [
    {
      "Key": "roll.value",
      "Value": {
        "Type": "INT64",
        "Value": 1
      }
    }
  ],
  "Events": null,
  "Links": null,
  "Status": {
    "Code": "Unset",
    "Description": ""
  },
  "DroppedAttributes": 0,
  "DroppedEvents": 0,
  "DroppedLinks": 0,
  "ChildSpanCount": 0,
  "Resource": [
    {
      "Key": "service.name",
      "Value": {
        "Type": "STRING",
        "Value": "dice"
      }
    },
    {
      "Key": "service.version",
      "Value": {
        "Type": "STRING",
        "Value": "0.1.0"
      }
    },
    {
      "Key": "telemetry.sdk.language",
      "Value": {
        "Type": "STRING",
        "Value": "go"
      }
    },
    {
      "Key": "telemetry.sdk.name",
      "Value": {
        "Type": "STRING",
        "Value": "opentelemetry"
      }
    },
    {
      "Key": "telemetry.sdk.version",
      "Value": {
        "Type": "STRING",
        "Value": "1.32.0"
      }
    }
  ],
  "InstrumentationScope": {
    "Name": "go.opentelemetry.io/otel/example/dice",
    "Version": "",
    "SchemaURL": "",
    "Attributes": null
  },
  "InstrumentationLibrary": {
    "Name": "go.opentelemetry.io/otel/example/dice",
    "Version": "",
    "SchemaURL": "",
    "Attributes": null
  }
}
{
  "Name": "/",
  "SpanContext": {
    "TraceID": "34a760f24420c2d0c1a7ad7d6a8ef814",
    "SpanID": "9c39e2a2f661e792",
    "TraceFlags": "01",
    "TraceState": "",
    "Remote": false
  },
  "Parent": {
    "TraceID": "00000000000000000000000000000000",
    "SpanID": "0000000000000000",
    "TraceFlags": "00",
    "TraceState": "",
    "Remote": false
  },
  "SpanKind": 2,
  "StartTime": "2024-11-29T11:50:39.808892+08:00",
  "EndTime": "2024-11-29T11:50:39.809416+08:00",
  "Attributes": [
    {
      "Key": "http.method",
      "Value": {
        "Type": "STRING",
        "Value": "GET"
      }
    },
    {
      "Key": "http.scheme",
      "Value": {
        "Type": "STRING",
        "Value": "http"
      }
    },
    {
      "Key": "net.host.name",
      "Value": {
        "Type": "STRING",
        "Value": "127.0.0.1"
      }
    },
    {
      "Key": "net.host.port",
      "Value": {
        "Type": "INT64",
        "Value": 10081
      }
    },
    {
      "Key": "net.sock.peer.addr",
      "Value": {
        "Type": "STRING",
        "Value": "127.0.0.1"
      }
    },
    {
      "Key": "net.sock.peer.port",
      "Value": {
        "Type": "INT64",
        "Value": 50089
      }
    },
    {
      "Key": "user_agent.original",
      "Value": {
        "Type": "STRING",
        "Value": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
      }
    },
    {
      "Key": "http.target",
      "Value": {
        "Type": "STRING",
        "Value": "/trace/Alice"
      }
    },
    {
      "Key": "net.protocol.version",
      "Value": {
        "Type": "STRING",
        "Value": "1.1"
      }
    },
    {
      "Key": "http.route",
      "Value": {
        "Type": "STRING",
        "Value": "/trace/{player}"
      }
    },
    {
      "Key": "http.wrote_bytes",
      "Value": {
        "Type": "INT64",
        "Value": 2
      }
    },
    {
      "Key": "http.status_code",
      "Value": {
        "Type": "INT64",
        "Value": 200
      }
    }
  ],
  "Events": null,
  "Links": null,
  "Status": {
    "Code": "Unset",
    "Description": ""
  },
  "DroppedAttributes": 0,
  "DroppedEvents": 0,
  "DroppedLinks": 0,
  "ChildSpanCount": 1,
  "Resource": [
    {
      "Key": "service.name",
      "Value": {
        "Type": "STRING",
        "Value": "dice"
      }
    },
    {
      "Key": "service.version",
      "Value": {
        "Type": "STRING",
        "Value": "0.1.0"
      }
    },
    {
      "Key": "telemetry.sdk.language",
      "Value": {
        "Type": "STRING",
        "Value": "go"
      }
    },
    {
      "Key": "telemetry.sdk.name",
      "Value": {
        "Type": "STRING",
        "Value": "opentelemetry"
      }
    },
    {
      "Key": "telemetry.sdk.version",
      "Value": {
        "Type": "STRING",
        "Value": "1.32.0"
      }
    }
  ],
  "InstrumentationScope": {
    "Name": "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp",
    "Version": "0.49.0",
    "SchemaURL": "",
    "Attributes": null
  },
  "InstrumentationLibrary": {
    "Name": "go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp",
    "Version": "0.49.0",
    "SchemaURL": "",
    "Attributes": null
  }
}
```

## 将追踪数据发往 OTel Collector

OTel Collector 是大多数生产部署中一个关键的组件。以下是一些使用 OTel Collector 的优势：
- 一个由多个服务共享的单一可观测数据收集器，以减少切换 Exporter 的开销
- 在发往服务端之前可以集中处理 trace，避免重复处理操作
- 可以聚合多个服务、多个主机上的 Trace


除非您只有一个服务或正在进行测试，否则在生产部署中，推荐您使用收集器

### 上报至本地 OTel Collector

```go
func newPrometheusMeterProvider() (*metric.MeterProvider, error) {
    metricExporter, err := otlpmetricgrpc.New(
       context.Background(),
       otlpmetricgrpc.WithInsecure(),
       otlpmetricgrpc.WithEndpoint("0.0.0.0:4317"))
    if err != nil {
       return nil, err
    }

    return metric.NewMeterProvider(
       metric.WithReader(
          metric.NewPeriodicReader(
             metricExporter,
             // Default is 1m. Set to 3s for demonstrative purposes.
             metric.WithInterval(3*time.Second))),
    ), nil
}
```

### 配置并启动一个本地的 OTel Collector

首先，将以下 OTel Collector 配置代码保存到 /tmp/otel-collector-config.yaml 文件中：

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4319
      http:
        endpoint: 0.0.0.0:4320
exporters:
  NOTE: Prior to v0.86.0 use logging instead of debug.
  debug:
    verbosity: detailed
processors:
  batch:
service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [debug]
      processors: [batch]
    metrics:
      receivers: [otlp]
      exporters: [debug]
      processors: [batch]
    logs:
      receivers: [otlp]
      exporters: [debug]
      processors: [batch]
```

- service 配置了服务相关的参数，这里定义了追踪数据的 pipeline。该 pipeline 使用了前面定义的接收器、处理器和导出器，将追踪数据从接收器接收、经过处理器处理，最终导出。

以上配置将使用 otlp 协议来接收用户的输入，即 OTel Go SDK 与 OTel Collector 之间使用 otlp 协议进行通信。并将数据最终打印在 OTel Collector 控制台。您也可以将数据上报至于 Prometheus 或者 Jaeger 中，详细的配置信息见：[OTel Collector配置](https://opentelemetry.io/docs/collector/)

然后运行 Docker 命令，根据此配置获取并运行 OTel Collector：

Terminal window

```shell
docker run -p 4320:4320 \
  -v /tmp/otel-collector-config.yaml:/etc/otel-collector-config.yaml \
  otel/opentelemetry-collector:latest \
  --config=/etc/otel-collector-config.yaml
```

您现在将在本地运行一个 OTel Collector 实例，该实例监听 4320 端口。

#### 运行 Demo
对应 Trace 信息会显示到启动的 OTel Collector 实例终端。

Terminal window
```shell
export OTEL_EXPORTER_OTLP_ENDPOINT="0.0.0.0:4320"
```
https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/examples/demo

## 将链路追踪数据直接发送至 Jaeger

如果觉着控制台看的 span 不够直观，可以选择将链路追踪的数据发送至 Jaeger，通过 Jaeger UI 查看。

### 上报至 Jaeger

安装 otlptracehttp 依赖包。

```shell
go get go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp
```

修改 otel.go 代码，新增以下函数（这里使用 HTTP 协议的4318 端口上报链路追踪数据）。

```go
func newJaegerTraceProvider(ctx context.Context) (*trace.TracerProvider, error) {
        // 创建一个使用 HTTP 协议连接本机Jaeger的 Exporter
        traceExporter, err := otlptracehttp.New(ctx,
                otlptracehttp.WithEndpoint("127.0.0.1:4318"),
                otlptracehttp.WithInsecure())
        if err != nil {
                return nil, err
        }
        traceProvider := trace.NewTracerProvider(
                trace.WithBatcher(traceExporter,
                        // 默认为 5s。为便于演示，设置为 1s。
                        trace.WithBatchTimeout(time.Second)),
        )
        return traceProvider, nil
}
```

并且按如下代码修改设置 trace provider 部分。

```go
// 设置 trace provider.
//tracerProvider, err := newTraceProvider()
tracerProvider, err := newJaegerTraceProvider(ctx)
if err != nil {
        handleErr(err)
        return}
shutdownFuncs = append(shutdownFuncs, tracerProvider.Shutdown)
otel.SetTracerProvider(tracerProvider)
```

再次构建并启动程序。
```shell
  go run .
```

尝试访问一次 http://localhost:10081/rolldice/Alice，确保修改后的服务能够正常运行。

### 启动 Jaeger

Jaeger 官方提供的 all-in-one 是为快速本地测试而设计的可执行文件。它包括 Jaeger UI、jaeger-collector、jaeger-query 和 jaeger-agent，以及一个内存存储组件。

启动 all-in-one 的最简单方法是使用发布到 DockerHub 的预置镜像（只需一条命令行）。

通过 4317 端口接收 OTel Collector 发送的数据，这里使用 HTTP 协议的4318 端口上报链路追踪数据。

```shell
docker run -d --name jaeger \
  -e COLLECTOR_OTLP_ENABLED=true \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  jaegertracing/all-in-one:latest
```

下面这个是其它案例里面的操作：

```shell
docker run --rm --name jaeger \
  -e COLLECTOR_ZIPKIN_HOST_PORT=:9411 \
  -p 6831:6831/udp \
  -p 6832:6832/udp \
  -p 5778:5778 \
  -p 16686:16686 \
  -p 4317:4317 \
  -p 4318:4318 \
  -p 14250:14250 \
  -p 14268:14268 \
  -p 14269:14269 \
  -p 9411:9411 \
  jaegertracing/all-in-one:1.55
```

容器公开以下端口：

| Port  | Protocol | Component | Function                                                                 |
|-------|:--------:|-----------|-------------------------------------------------------------------------|
| 6831  | UDP      | agent     | accept jaeger.thrift over Thrift-compact protocol (used by most SDKs)   |
| 6832  | UDP      | agent     | accept jaeger.thrift over Thrift-binary protocol (used by Node.js SDK)  |
| 5775  | UDP      | agent     | (deprecated) accept zipkin.thrift over compact Thrift protocol          |
| 5778  | HTTP     | agent     | serve configs (sampling, etc.)                                         |
| 16686 | HTTP     | query     | serve frontend                                                         |
| 4317  | HTTP     | collector | accept OpenTelemetry Protocol (OTLP) over gRPC                          |
| 4318  | HTTP     | collector | accept OpenTelemetry Protocol (OTLP) over HTTP                          |
| 14268 | HTTP     | collector | accept jaeger.thrift directly from clients                             |
| 14250 | HTTP     | collector | accept model.proto                                                     |
| 9411  | HTTP     | collector | Zipkin compatible endpoint (optional)                                  |

#### 查看数据

然后你可以使用浏览器打开 http://localhost:16686 访问 Jaeger UI。

### 使用 Jaeger UI
使用浏览器打开 http://127.0.0.1:16686 的Jaeger UI界面。 在屏幕左侧的 service 下拉框中选中 dice后查找，即可看到上报的 trace 数据。

![图1 TiDB Server 1流程图](/images/otel/jeager-search.png)

点击右侧的 trace 数据，即可查看详情。

![图2 trace 数据图](/images/otel/jaeger-trace.png)

查看火焰图等格式

![图3 火焰图](/images/otel/jaeger-flamegragh.png)

## 将追踪数据发送至 Prometheus（通过 OTel Collector）

### 上报本地的 OTel Collector


```go
func newPrometheusMeterProvider() (*metric.MeterProvider, error) {
    metricExporter, err := otlpmetricgrpc.New(
       context.Background(),
       otlpmetricgrpc.WithInsecure(),
       otlpmetricgrpc.WithEndpoint("0.0.0.0:4317"))
    if err != nil {
       return nil, err
    }

    return metric.NewMeterProvider(
       metric.WithReader(
          metric.NewPeriodicReader(
             metricExporter,
             // Default is 1m. Set to 3s for demonstrative purposes.
             metric.WithInterval(3*time.Second))),
    ), nil
}
```

### 配置并启动一个本地的 OTel Collector

首先，将以下 OTel Collector 配置代码保存到 /tmp/otel-collector-config.yml 文件中：

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4320
exporters:
  prometheus:
    endpoint: "0.0.0.0:8889"
    const_labels:
      label1: value1
  debug:
    verbosity: detailed
processors:
  batch:
service:
  pipelines:
    traces:
      receivers: [otlp]
      exporters: [debug]
      processors: [batch]
    metrics:
      receivers: [otlp]
      exporters: [debug, prometheus]
      processors: [batch]
    logs:
      receivers: [otlp]
      exporters: [debug]
      processors: [batch]
```

运行 OTel Collector

```shell
docker run -p 4320:4320 \
  -p 4317:4317 \      # OTLP gRPC receiver
  -p 8888:8888 \      # Prometheus metrics exposed by the collector
  -p 8889:8889 \      # Prometheus exporter metrics
  -v /tmp/otel-collector-config.yaml:/etc/otel-collector-config.yaml \
  otel/opentelemetry-collector:latest \
  --config=/etc/otel-collector-config.yaml
```

### 配置并启动 Prometheus

prometheus.yml 文件

```yaml
  scrape_configs:
    - job_name: 'otel-collector'
      scrape_interval: 10s
      static_configs:
        - targets: ['otel-collector:8889']
        - targets: ['otel-collector:8888']
```

如果上面的 yml 文件配置了 targets.json 文件（以 TiDB 集群配置为例），则需要改 .../prometheus/targets.json
```yaml
    ## Prometheus.yml
    scrape_configs:
      - job_name: 'cluster'
        file_sd_configs:
          - files:
              - targets.json
```

``` json
// prometheus/targets.json
    {
            "targets": [
                    "127.0.0.1:8889"
            ],
            "labels": {
                    "job": "otel-collector"
            }
    },
    {
            "targets": [
                    "127.0.0.1:8888"
            ],
            "labels": {
                    "job": "otel-collector"
            }
    },
```

启动 prometheus，以下是以 TiDB 集群启动 prometheus 为例

```shell
./prometheus --config.file=/Users/xia/.tiup/data/UVx5Syf/prometheus/prometheus.yml --web.external-url=http://127.0.0.1:9090 --web.listen-address=127.0.0.1:9090 --storage.tsdb.path=/Users/xia/.tiup/data/UVx5Syf/prometheus/data
```

### Prometheus 显示

查看配置是否正确，http://127.0.0.1:9090/targets?search=

![图4 Prometheus](/images/otel/prometheus-conf.png)

上面 Prometheus 配置 job name，{job="otel-collector"}
[http://128.0.0.1:9090 job search](http://127.0.0.1:9090/graph?g0.expr=%7Bjob%3D%22otel-collector%22%7D&g0.tab=1&g0.display_mode=lines&g0.show_exemplars=0&g0.range_input=1h&g0.end_input=2024-12-04%2008%3A37%3A23&g0.moment_input=2024-12-04%2008%3A37%3A23)

![图5 Prometheus job](/images/otel/prometheus-job.png)


## 参考

- [OpenTelemetry Go快速指南](https://www.liwenzhou.com/posts/Go/openTelemetry-go/)
- [Golang 语言快速开始](https://observability.cn/project/opentelemetry/gbbir8vid2gqibid/#_top)