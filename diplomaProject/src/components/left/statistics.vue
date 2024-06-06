<template>
<div>
  <h6 style="margin-block-start: 0; margin-block-end: 0;">FEATURES OVERVIEW VIEW</h6>
  <div id="myChart1"></div>
</div>
</template>

<script>
import echarts from "echarts";
export default {
  name: "statistics",
  data() {
    return {
        staticsDt: ''
    };
  },
  mounted() {
    this.$axios({
        method:"get",
        url: '/statisticsDt'
    }).then(res =>{
        this.staticsDt = res.data
        this.drawStatistics(this.staticsDt);
    })
      .catch(reason => {
        console.log(reason);
      });
  },
  methods: {
    drawStatistics(data) {
      let myChart = echarts.init(document.getElementById("myChart1"),null, {renderer: 'svg'});
      // Generate data
      var category = data[0]
      var barData = data[1]
      var rateData = data[2]
      var rateData1 = data[3]
        console.log(data[0])
        console.log(data[1])
        console.log(data[2])
        console.log(data[3])
      // option
      let option = {
        title: {
          x: "center",
          y: 0,
          textStyle: {
            color: "#B4B4B4",
            fontSize: 12,
            fontWeight: "normal"
          }
        },
        backgroundColor: "#ffffff",
        tooltip: {
          trigger: "axis",
          backgroundColor: "#f0f0f0",
          axisPointer: {
            type: "shadow",
            label: {
              show: true,
              backgroundColor: "#7B7DDC"
            }
          },
          textStyle: {
            // 提示框浮层的文本样式。
            color: "#000",
            fontStyle: "normal",
            fontWeight: "normal",
            fontFamily: "sans-serif",
            fontSize: 8
          }
        },
        legend: {
          data: ["ncloc", "files", "issues"],
          textStyle: {
            color: "#1e1e1e",
            fontSize: 8
          },
          top: "2%"
        },
        grid: {
          x: "10%",
          width: "82%",
          y: "20%"
        },
        xAxis: {
          data: category,
          axisLine: {
            lineStyle: {
              color: "#B4B4B4",
              fontSize: 8
            }
          },
          axisTick: {
            show: false
          },
            axisLabel: {
                textStyle: {
                  color: '#1e1e1e',  //更改坐标轴文字颜色
                  fontSize : 10      //更改坐标轴文字大小
                }
            }
        },
        yAxis: [
          {
            splitLine: {
              show: false
            },
            axisLine: {
              lineStyle: {
                color: "#B4B4B4",
                fontSize: 4
              }
            },

            axisLabel: {
              formatter: "{value} ",
                textStyle: {
                  color: '#1e1e1e',  //更改坐标轴文字颜色
                  fontSize : 8      //更改坐标轴文字大小
                }
            }
          },
          {
            splitLine: {
              show: false
            },
            axisLine: {
              lineStyle: {
                color: "#B4B4B4",
                fontSize: 8
              }
            },
            axisLabel: {
              formatter: "{value} ",
                textStyle: {
                  color: '#1e1e1e',  //更改坐标轴文字颜色
                  fontSize : 8      //更改坐标轴文字大小
                }
            }
          }
        ],
        series: [
          {
            name: "ncloc",
            type: "bar",
            barWidth: 1,
            itemStyle: {
              normal: {
                barBorderRadius: 1,
                color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                  {
                    offset: 0,
                    color: "#956FD4"
                  },
                  {
                    offset: 1,
                    color: "#3EACE5"
                  }
                ])
              }
            },
            data: barData
          },
          {
            name: "files",
            type: "line",
            smooth: false,
            showAllSymbol: true,
            symbol: "emptyCircle",
            symbolSize: 2,
            yAxisIndex: 1,
            itemStyle: {
              normal: {
                color: "#e0a009",
                lineStyle: {
                  width: 1 //设置线条粗细
                }
              }
            },
            data: rateData
          },
          {
            name: "issues",
            type: "line",
            smooth: false,
            showAllSymbol: true,
            symbol: "emptyCircle",
            symbolSize: 2,
            yAxisIndex: 1,
            itemStyle: {
              normal: {
                color: "#a3caeb",
                lineStyle: {
                  width: 1 //设置线条粗细
                }
              }
            },
            data: rateData1
          }
        ]
      };
      myChart.setOption(option, true);
      myChart.resize({ width: 400, height: 270 });
    }
  }
};
</script>
