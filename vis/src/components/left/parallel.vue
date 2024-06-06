<template>
  <div>
    <h6 style="margin-block-start: 0; margin-block-end: 0;">TOP TAGS VIEW</h6>
  <div id="myChart" style="width: '300px', height: '400px'"></div>
  </div>
</template>

<script>
import echarts from 'echarts'

export default {
  name: "tagView",
  data() {
    return {
        parallelDt: [],
        v1: '',
        v2: ''
    };
  },
  methods: {
    initTagView() {
      if(this.$store.state.isComparison == false){  // 不是在比较模式下
        this.v1 = this.$store.state.singleVersion   // 在非比较模式下选择第一个输入框的值
        this.v2 = ''
      }
      else if(this.$store.state.isComparison == true){
        this.v1 = this.$store.state.twoVersion1   // 在比较模式下选择第一个和第二个输入框的值
        this.v2 = this.$store.state.twoVersion2
      }

    this.$axios({
        method: "post",
        url: "/tagDt",
        data: {
          v1: this.v1, // 文件路径和文件名
          v2: this.v2 // 文件的版本号
        }
      })
        .then(res => {
          this.parallelDt = res.data;
          this.draw(this.parallelDt);
        })
        .catch(reason => {
          console.log(reason);
        });
    
    },
    draw(data){
      var _this = this
      // 基于准备好的dom，初始化echarts实例
      let myChart = echarts.init(document.getElementById("myChart"),null, {renderer: 'svg'});
      var option = {
        // backgroundColor: '#333',
        legend: {
          top: 10,
          left: 8,
          data: [],
          itemGap: 20,
          textStyle: {
            color: "#333",
            fontSize: 10
          }
        },
        grid: {
          top: 28,
          left: 24,
          bottom: 24,
          right: 24
        },
        parallelAxis: [],
        parallel: {
          left: 20,
          top: 60,
          layout:'vertical',
          parallelAxisDefault: {
            type: "value",
            name: "Tag",
            nameLocation: "end",
            nameGap: 10,
            nameTextStyle: {
              color: "#333",
              fontSize: 10
            },
            axisLine: {
              lineStyle: {
                color: "#aaa",
                fontSize: 4
              }
            },
            axisTick: {
              lineStyle: {
                color: "#333",
                fontSize: 4
              }
            },
            splitLine: {
              show: false
            },
            axisLabel: {
              textStyle: {
                color: "#333",
                fontSize: 8
              }
            }
          }
        },
        series: []
      };

      if(_this.v2 == ''){   // 是在一个版本的情况下
        let seriesDt = []
        for(let i=0; i<data.length; i++){
            seriesDt.push(data[i][1])
            option['parallelAxis'].push({dim: i, name: data[i][0]})
        }
        // 设置 option
        seriesDt.push(_this.v1.split('--')[1] )    // 将版本号加进去
        option['parallelAxis'].push({dim: data.length, type: "category", name: '版本'})
        option['legend']['data'].push(_this.v1.split('--')[1])
        option['series'].push({name:_this.v1.split('--')[1] , type:"parallel", lineStyle: {normal: {width: 1,opacity: 0.5,color: '#ff9800'}}, data: [seriesDt]})
      }else{
        let seriesDt1 = []
        let seriesDt2 = []
        for(let i=0; i< data['v1'].length; i++){
            seriesDt1.push(data['v1'][i][1])
            seriesDt2.push(data['v2'][i][1])
            option['parallelAxis'].push({dim: i, name: data['v1'][i][0]})
        }
        // 设置 option
        seriesDt1.push(_this.v1.split('--')[1] )    // 将版本号加进去
        seriesDt2.push(_this.v2.split('--')[1] )    // 将版本号加进去
        option['parallelAxis'].push({dim: data.length, type: "category", name: '版本'})
        option['legend']['data'].push(_this.v1.split('--')[1])
        option['legend']['data'].push(_this.v2.split('--')[1])
        option['series'].push({name:_this.v1.split('--')[1] , type:"parallel", lineStyle: {normal: {width: 1,opacity: 0.5,color: '#ff9800'}}, data: [seriesDt1]})
        option['series'].push({name:_this.v2.split('--')[1] , type:"parallel", lineStyle: {normal: {width: 1,opacity: 0.5,color: '#a3caeb'}}, data: [seriesDt2]})
      }

      // 设置数据
      myChart.setOption(option, true)
      myChart.resize({ width: 400, height: 400 });
    }
  }
};
</script>

