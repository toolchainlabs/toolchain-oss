package proxy

import (
	"net/http"
	"strconv"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	requestsCounter = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "aws_es_proxy_requests_http_total",
		Help: "The total number of processed requests",
	}, []string{"method", "status"})
)

func reportRequest(status int, req *http.Request) {
	requestsCounter.With(prometheus.Labels{"status": strconv.Itoa(status), "method": req.Method}).Inc()
}
