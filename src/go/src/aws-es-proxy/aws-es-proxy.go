package main

import (
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"runtime"

	"github.com/prometheus/client_golang/prometheus/promhttp"
	proxy "github.com/toolchainlabs/toolchain/src/go/aws-es-proxy/proxy"
)

var (
	// Set during go build
	gitCommit string
)

func main() {
	var (
		verbose       bool
		prettify      bool
		logtofile     bool
		nosignreq     bool
		procs         int
		endpoint      string
		listenAddress string
		assumeRole    string
		metricsListen string
		fileRequest   *os.File
		fileResponse  *os.File
		err           error
	)
	flag.StringVar(&endpoint, "endpoint", "", "Amazon ElasticSearch Endpoint (e.g: https://dummy-host.eu-west-1.es.amazonaws.com)")
	flag.StringVar(&listenAddress, "listen", "127.0.0.1:9200", "Local TCP port to listen on")
	flag.StringVar(&metricsListen, "metrics", "", "Local TCP port to listen on for prometheus metrics")
	flag.StringVar(&assumeRole, "assume", "", "Optionally specify role to assume")
	flag.BoolVar(&verbose, "verbose", false, "Print user requests")
	flag.BoolVar(&logtofile, "log-to-file", false, "Log user requests and ElasticSearch responses to files")
	flag.BoolVar(&prettify, "pretty", false, "Prettify verbose and file output")
	flag.BoolVar(&nosignreq, "no-sign-reqs", false, "Disable AWS Signature v4")
	flag.IntVar(&procs, "procs", 0, "Max number of threads/procs in the goroutines threadpool (sets GOMAXPROCS)")
	flag.Parse()

	if len(os.Args) < 3 {
		fmt.Println("You need to specify Amazon ElasticSearch endpoint.")
		fmt.Println("Please run with '-h' for a list of available arguments.")
		os.Exit(1)
	}
	if procs > 0 {
		runtime.GOMAXPROCS(procs)
	}
	maxProcs := runtime.GOMAXPROCS(-1)
	log.Printf("Starting AWS ES Proxy GitCommit=%v GOMAXPROCS=%v", gitCommit, maxProcs)

	p := proxy.NewProxy(
		endpoint,
		verbose,
		prettify,
		logtofile,
		nosignreq,
		assumeRole,
	)

	if err = p.ParseEndpoint(); err != nil {
		log.Fatalln(err)
		os.Exit(1)
	}
	p.InitLog(fileRequest, fileResponse)
	go startMetricsServer(metricsListen)
	log.Printf("Listening on %s...\n", listenAddress)
	log.Fatal(http.ListenAndServe(listenAddress, p))
}

func startMetricsServer(metricsEP string) {
	if metricsEP == "" {
		return
	}
	log.Printf("metrics %v", metricsEP)
	http.Handle("/metrics", promhttp.Handler())
	http.ListenAndServe(":"+metricsEP, nil)
}
