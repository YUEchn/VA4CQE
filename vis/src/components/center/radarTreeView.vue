<!--
 * @Descripttion: 
 * @version: 
 * @Author: Yolanda
 * @Date: 2021-04-15 16:21:57
 * @LastEditors: Yolanda
 * @LastEditTime: 2021-04-20 10:01:29
-->
<template>
  <div>
    <div style="float:left; height:100%">
    <button type="button" class = "singleButton" @click="showFilename()">Show Filename!</button>
    </div>
    <div id="box" style="padding-left:100px; float:left;"></div>
  </div>
</template>

<script>
import * as d3 from "d3";

export default {
  name: "radarTreeView",
  data() {
    return {
      mainData: "",
      margins: { top: 0, left: 50, bottom: 0, right: 50 },
      textColor: "black",
      title: "径向树图",
      hoverColor: "#ff7e00",
      animateDuration: 1000,
      pointSize: 5,
      pointFill: "#c8b0e4",
      pointStroke: "transparent",
      lineStroke: "gray",
      width: 500,
      height: 300,
      oldX: 0,
      oldY: 0,
      targetNode: "",
      first: "",
      svg: "",
      nodeId: 0,
      radarG: "",
      tooltip: "",
      diameter: 170, // 树图的直径,
      radarData: [],
      bugMax: 0,
      code_smellMax: 0,
      vulnerabilityMax: 0,
      ccMax: 0,
      dlMax: 0,
      clMax: 0,
      tooltipHtml: "",
      versionNumber: this.$store.state.singleVersion,
      btnClick:0
    };
  },
  computed: {
    // 监听全局变量的时候使用这种方法
    isChangeSingleVersion() {
      return this.$store.state.singleVersion;
    }
  },

  watch: {
    isChangeSingleVersion: function() {
      // 监听这个函数的返回内容
      this.initRadarTree();
    }
  },
  methods: {
    // 初始化雷达树图的数据
    initRadarTree() {
      let vm = this;
      this.versionNumber = this.$store.state.singleVersion;
      vm.$axios({
        method: "post",
        url: "/radarTreeDt",
        data: {
          versionNumber: this.versionNumber
        }
      })
        .then(res => {
          this.mainData = res.data;
          this.drawRadarTreeView(this.mainData);

          vm.tooltipHtml = d3.select(".tooltipHtml")
          if(vm.tooltipHtml._groups[0][0] == null){
            vm.tooltipHtml = d3.select("#box")
            .append("div")
            .attr("class", "tooltipHtml")
            .style("opacity", 0);
          }
        })
        .catch(reason => {
          console.log(reason);
        });
    },

    drawRadarTreeView(Maindata) {
      var _this = this;
      const root = d3.hierarchy(Maindata);
      const generateTree = d3
        .cluster()
        .nodeSize([10, 10])
        .separation((a, b) => (a.parent === b.parent ? 1 : 1))
        // .size([2 * Math.PI, 180]);
        .size([2 * Math.PI, _this.diameter]);
      generateTree(root);

      function renderNode() {
        let nodes = d3.select(".groups");
        if (nodes.empty()) {
          nodes = d3
            .select(".body")
            .append("g")
            .attr("class", "groups")
            .attr(
              "transform",
              "translate(" + _this.width / 2 + "," + _this.height / 2 + ")"
            );
        }

        const groups = nodes
          .selectAll(".g")
          .data(root.descendants(), d => d.id || (d.id = ++_this.nodeId));

        var groupsEnter = groups
          .enter()
          .append("g")
          .attr("class", function(d) {
            let classname;
            if (typeof d.data.fileDir != "undefined") {
              classname = "g " + d.data.fileDir;
            } else {
              classname = "g #" + d.data.title;
            }
            return classname;
          })
          .on("mouseover", function(d) {
            let ddHtml = d3.select(this)._groups[0][0].__data__;
            var toolY = 0,
              toolX = 0;
            _this.tooltipHtml
              .html(d => {
                toolX = d3.event.clientX - 300;
                toolY = d3.event.clientY - 300;

                let filename = ddHtml.data.title;
                let ncloc = ddHtml.data.metrics.lines;
                let cc = ddHtml.data.metrics.cognitive_complexity;
                let cld = ddHtml.data.metrics.comment_lines_density;
                let bug = ddHtml.data.metrics.bugs;
                let code_smell = ddHtml.data.metrics.code_smells;
                let vulnerability = ddHtml.data.metrics.vulnerabilities;
                let dld = ddHtml.data.metrics.duplicated_lines_density;
                let str =
                  filename +
                  "<br/>" +
                  "ncloc: " + ncloc +
                  "<br/>" +
                  "cognitive_complexity: " + cc +
                  "<br/>" +
                  "comment_lines_density:" +
                  cld +
                  "<br/>" +
                  "bugs: " +
                  bug +
                  "<br/>" +
                  "code_smells: " +
                  code_smell +
                  "<br/>" +
                  "vulnerability: " +
                  vulnerability +
                  "<br/>" +
                  "duplicated_lines_density: " +
                  dld +
                  "<br/>";
                return str;
              })
              .style("left", toolX + "px")
              .style("top", toolY + "px")
              .style("font-size", "12px")
              .style("color", "white")
              .style("opacity", 1)
              .style("position", "absolute")
              .style("width", "auto")
              .style("height", "auto")
              .style("border-radius", "5px")
              .style("background", "#84b6d1");

            if (d.children != null) {
              d3.select(d3.select(this)._groups[0][0].lastChild).attr(
                "opacity",
                1
              ); // 显示指标名称
            }
          })
          .on("mouseout", function(d) {
            _this.tooltipHtml.style("opacity", 0);
            if (d.children != null) {
              d3.select(d3.select(this)._groups[0][0].lastChild).attr(
                "opacity",
                0
              );
            }
          })
          .attr("transform", (d, i) => {
            // 用真实数据初始化雷达图的数据
            _this.radarData[i] = [
              { key: "bugs", value: d.data.metrics.bugs },
              { key: "code_smells", value: d.data.metrics.code_smells },
              { key: "vulnerabilities", value: d.data.metrics.vulnerabilities },
              {
                key: "duplicated_lines_density",
                value: d.data.metrics.duplicated_lines_density
              },
              {
                key: "cognitive_complexity",
                value: d.data.metrics.cognitive_complexity
              },
              {
                key: "comment_lines_density",
                value: d.data.metrics.comment_lines_density
              },
              {
                key: "lines", ///////增加的内容//////
                value: d.data.metrics.lines
              },
              {
                key: "title",
                value: d.data.title
              },
              {
                key: "value",
                value: d.data.value
              }
            ];
            _this.bugMax = Math.max(_this.bugMax, d.data.metrics.bugs);
            _this.code_smellMax = Math.max(
              _this.code_smellMax,
              d.data.metrics.code_smells
            );
            _this.vulnerabilityMax = Math.max(
              _this.vulnerabilityMax,
              d.data.metrics.vulnerabilities
            );
            _this.ccMax = Math.max(
              _this.ccMax,
              d.data.metrics.cognitive_complexity
            );
            _this.dlMax = Math.max(
              _this.dlMax,
              d.data.metrics.duplicated_lines_density
            );
            _this.clMax = Math.max(
              _this.clMax,
              d.data.metrics.comment_lines_density
            );
            if (_this.first)
              return (
                "translate(" +
                _this.oldY * Math.cos(_this.oldX - Math.PI / 2) +
                "," +
                _this.oldY * Math.sin(_this.oldX - Math.PI / 2) +
                ")"
              ); //首次渲染，子树从（0，0）点开始放缩，否则，从点击位置开始放缩
          });

        /////////////////////////雷达图初始数据//////////////////////////////////////
        var axi_circle_point_num = 6; //极坐标的点数
        var axi_circle_num = 4; //坐标画几个圈
        var axi_circle_step;
        if (_this.radarData.length >= 25) {
          axi_circle_step = 3; //坐标轴的每一步长度
        } else {
          axi_circle_step = 5; //坐标轴的每一步长度
        }
        let angles = d3.range(
          Math.PI / 6,
          2 * Math.PI + Math.PI / 6,
          (2 * Math.PI) / axi_circle_point_num
        );
        //////////////////////////////////定义不同的比例尺////////////////////////
        let scale = d3 // 代码异味的比例尺
          .scaleLinear()
          .domain([0, _this.code_smellMax])
          .range([0, axi_circle_num * axi_circle_step]);
        let ccscale = d3 // 认知复杂度的比例尺
          .scaleLinear()
          .domain([0, _this.ccMax])
          .range([0, axi_circle_num * axi_circle_step]);
        let bscale = d3 // bug 的比例尺
          .scaleLinear()
          .domain([0, _this.bugMax])
          .range([0, axi_circle_num * axi_circle_step]);
        let vscale = d3 // 漏洞的比例尺
          .scaleLinear()
          .domain([0, _this.vulnerabilityMax])
          .range([0, axi_circle_num * axi_circle_step]);
        let dlscale = d3 // 重复行密度比例尺
          .scaleLinear()
          .domain([0, _this.dlMax])
          .range([0, axi_circle_num * axi_circle_step]);
        let clscale = d3 // 注释行密度比例尺
          .scaleLinear()
          .domain([0, _this.clMax])
          .range([0, axi_circle_num * axi_circle_step]);

        _this.radarG = groupsEnter
          .append("g") // 增加存放雷达图的g
          .attr("class", function(d, i) {
            return "radarG-" + i;
          });
        // 更改的内容: 设置每一个元素的背景
        if (_this.radarData.length > 25) {
          _this.radarG
            .append("circle")
            .attr("cx", "0")
            .attr("cy", "0")
            .attr("r", "15")
            .attr("fill", "#fff");
        } else {
          _this.radarG
            .append("circle")
            .attr("cx", "0")
            .attr("cy", "0")
            .attr("r", "20")
            .attr("fill", "#fff");
        }

        console.log(
          _this.code_smellMax,
          _this.ccMax,
          _this.bugMax,
          _this.dlMax,
          _this.dlMax,
          _this.clMax
        );
        groupsEnter
          .merge(groups)
          .transition()
          .duration(_this.animateDuration)
          .attr("transform", d => {
            return (
              "translate(" +
              d.y * Math.cos(d.x - Math.PI / 2) +
              "," +
              d.y * Math.sin(d.x - Math.PI / 2) +
              ")"
            );
          });

        //绘制轴上的线条
        _this.radarG
          .append("g")
          .selectAll("polyline")
          .data(angles)
          .enter()
          .append("polyline")
          .attr("points", function(d, i) {
            let r = axi_circle_num * axi_circle_step,
              x = r * Math.cos(d),
              y = r * Math.sin(d);
            return `0,0 ${x},${y}`;
          })
          .attr("stroke", "#ccc")
          .attr("stroke-width", 1);
        // .attr("stroke-dasharray", "10 5");

        //绘制雷达图上面的点
        _this.radarG
          .append("g")
          .selectAll("circle")
          .data(angles) // 6个点
          .enter()
          .append("circle")
          .attr("class", function(d, i) {
            // 每个指标添加不同的类，便于区分和获取
            return "m-" + i + "-" + _this.radarData[0][i].key;
          })
          .attr("value", function(d, i) {
            // 添加value属性，表示每一个指标的值
            let fileNUmber = d3
              .select(this.parentNode.parentNode)
              .attr("class")
              .split("-")[1]; // 表示不同的文件
            return _this.radarData[fileNUmber][i].value;
          })
          .attr("cx", function(d, i) {
            var fileNUmber = d3
              .select(this.parentNode.parentNode)
              .attr("class")
              .split("-")[1]; // 表示不同的文件
            var x;
            if (_this.radarData[fileNUmber][i].key == "code_smells")
              x = scale(_this.radarData[fileNUmber][i].value) * Math.cos(d);
            // 代码异味的比例尺
            else if (
              _this.radarData[fileNUmber][i].key == "cognitive_complexity"
            )
              x = ccscale(_this.radarData[fileNUmber][i].value) * Math.cos(d);
            // 认知复杂度的比例尺
            else if (_this.radarData[fileNUmber][i].key == "bugs") {
              x = bscale(_this.radarData[fileNUmber][i].value) * Math.cos(d); // bug 的比例尺
            } else if (
              _this.radarData[fileNUmber][i].key == "vulnerabilities"
            ) {
              x = vscale(_this.radarData[fileNUmber][i].value) * Math.cos(d); // 漏洞的比例尺
            } else if (
              _this.radarData[fileNUmber][i].key == "duplicated_lines_density"
            ) {
              x = dlscale(_this.radarData[fileNUmber][i].value) * Math.cos(d); // 注释行 重复行密度的比例尺
            } else if (
              _this.radarData[fileNUmber][i].key == "comment_lines_density"
            ) {
              x = clscale(_this.radarData[fileNUmber][i].value) * Math.cos(d); // 注释行 重复行密度的比例尺
            }

            // console.log(_this.clMax,_this.code_smellMax,_this.ccMax,_this.bugMax,_this.dlMax)
            return x;
          })
          .attr("cy", function(d, i) {
            var fileNUmber = d3
              .select(this.parentNode.parentNode)
              .attr("class")
              .split("-")[1];
            var y;
            if (_this.radarData[fileNUmber][i].key == "code_smells")
              y = scale(_this.radarData[fileNUmber][i].value) * Math.sin(d);
            // 代码异味的比例尺
            else if (
              _this.radarData[fileNUmber][i].key == "cognitive_complexity"
            )
              y = ccscale(_this.radarData[fileNUmber][i].value) * Math.sin(d);
            // 认知复杂度的比例尺
            else if (_this.radarData[fileNUmber][i].key == "bugs")
              y = bscale(_this.radarData[fileNUmber][i].value) * Math.sin(d);
            // bug 的比例尺
            else if (_this.radarData[fileNUmber][i].key == "vulnerabilities")
              y = vscale(_this.radarData[fileNUmber][i].value) * Math.sin(d);
            // 漏洞的比例尺
            else if (
              _this.radarData[fileNUmber][i].key == "duplicated_lines_density"
            ) {
              y = dlscale(_this.radarData[fileNUmber][i].value) * Math.sin(d); // 注释行 重复行密度的比例尺
            } else if (
              _this.radarData[fileNUmber][i].key == "comment_lines_density"
            ) {
              y = clscale(_this.radarData[fileNUmber][i].value) * Math.sin(d); // 注释行 重复行密度的比例尺
            }
            return y;
          })
          .attr("r", 1)
          .attr("fill", "#CC333F")
          .style("pointer-events", "all")
          .on("mouseover", function(d) {
            // let newX = parseFloat(d3.select(this).attr("cx")) + 400;
            // let newY = parseFloat(d3.select(this).attr("cy")) + 100;
            // let newX = d3.event.x - 850;
            // let newY =
            //   d3.event.y - 800 <= 10
            //     ? 50
            //     : d3.event.y - 800 >= 430
            //     ? 420
            //     : d3.event.y - 800;
            // let filename = d3.select(
            //   d3.select(this)._groups[0][0].parentNode.parentNode.parentNode
            // )._groups[0][0].classList[1];
            // let metricNum = d3
            //   .select(this)
            //   .attr("class")
            //   .split("-")[1]; // 指标对应的索引，这里的i不是正常的i
            // let fileNUmber = d3
            //   .select(this.parentNode.parentNode)
            //   .attr("class")
            //   .split("-")[1];
            // let metricClass = d3
            //   .select(this)
            //   .attr("class")
            //   .split("-")[2];
            // _this.tooltip
            //   .attr("x", newX)
            //   .attr("y", newY)
            //   .attr("font-size", "12px")
            //   .text(
            //     metricClass + ":" + _this.radarData[fileNUmber][metricNum].value
            //   )
            //   .transition()
            //   .duration(200)
            //   .style("opacity", 1);
          })
          .on("mouseout", function() {
            // _this.tooltip
            //   .transition()
            //   .duration(200)
            //   .style("opacity", 1);
          });

        //绘制雷达图的线条及其填充区域，循环的次数为节点的数目，即文件的数目
        for (var k = 0; k < _this.radarG._groups[0].length; k++) {
          // k表示文件的索引号
          let lin = d3
            .lineRadial()
            .curve(d3.curveLinearClosed)
            .angle(d => {
              return d;
            })
            .radius((d, i) => {
              var r;
              if (_this.radarData[k][i].key == "code_smells")
                r = scale(_this.radarData[k][i].value);
              // 代码异味的比例尺
              else if (_this.radarData[k][i].key == "cognitive_complexity")
                r = ccscale(_this.radarData[k][i].value);
              // 认知复杂度的比例尺
              else if (_this.radarData[k][i].key == "bugs")
                r = bscale(_this.radarData[k][i].value);
              // 漏洞的比例尺
              else if (_this.radarData[k][i].key == "vulnerabilities")
                r = vscale(_this.radarData[k][i].value);
              // 漏洞的比例尺
              else if (
                _this.radarData[k][i].key == "duplicated_lines_density"
              ) {
                r = dlscale(_this.radarData[k][i].value); // 注释行 重复行密度的比例尺
              } else if (_this.radarData[k][i].key == "comment_lines_density") {
                r = clscale(_this.radarData[k][i].value); // 注释行 重复行密度的比例尺
              }
              return r; // 需要返回第k个文件的第i个指标
            });

          // console.log(d, d.data.metrics)
          d3.select(_this.radarG._groups[0][k])
            .append("g")
            .attr("class", "edge")
            .attr("transform", "rotate(90)")
            .append("path")
            .attr("d", lin(angles))
            .attr("stroke", "blue")
            .attr("stroke-width", 0.5)
            .attr("fill", "#EDC951")
            .style("opacity", "0.7")
            .on("mouseover", function(d) {
              d3.select(this)
                .transition()
                .duration(200)
                .style("opacity", "0.7");
            })
            .on("mouseout", function(d) {
              d3.select(this)
                .transition()
                .duration(200)
                .style("opacity", "0.7");
            });

          // 绘制指标名称
          // 指标的名称
          let metricNameArr = [
            "bug",
            "code smell",
            "vulnerability",
            "dld",
            "cc",
            "cld"
          ];
          d3.select(_this.radarG._groups[0][k])
            .append("g")
            // .attr("transform", "translate(" + margin.left + ',' + margin.top + ')')
            .selectAll("text")
            .data(angles)
            .enter()
            .append("text")
            .text(function(d, i) {
              console.log(metricNameArr[i], i);
              return metricNameArr[i];
            })
            .attr("font-size", "10px")
            .attr("font-weight", "bold")
            .attr("class", "metricName")
            .attr("transform", function(d, i) {
              let r = axi_circle_num * axi_circle_step,
                x = r * Math.cos(d),
                y = r * Math.sin(d);
              if (d > Math.PI / 2 && d < (Math.PI * 3) / 2) {
                // 左侧两个指标
                x -= 5;
              } else if (d == (Math.PI * 3) / 2) {
                // 顶部指标
                y -= 5;
              } else if (d == Math.PI / 2) {
                // 最底部的指标
                y += 8;
              } else {
                // 右侧两个指标
                x += 5;
              }
              return `translate(${x},${y})`;
            })
            .attr("opacity", "0")
            .attr("text-anchor", function(d, i) {
              if (d > Math.PI / 2 && d < (Math.PI * 3) / 2) {
                return "end";
              } else if (d == Math.PI / 2 || d == (Math.PI * 3) / 2) {
                return "middle";
              } else {
                return "start";
              }
            });
        }

        //////////////////////////////////////// 绘制外层的圆环/////////////////////////////////
        function drawPie() {
          //外半径和内半径
          var outerRadius = axi_circle_step * axi_circle_num + 2;
          var innerRadius = axi_circle_step * axi_circle_num;
          // 创建弧生成器
          var arc = d3
            .arc()
            .innerRadius(innerRadius) // 弧的外半径
            .outerRadius(outerRadius); // 弧的内半径

          //////////////////////////////////////更改的内容/////////////////////////////////////
          var pieLinedate = [];
          var pieLine = d3
            .pie() // 创建一个饼状图布局
            .value(function(d) {
              return d[0]; // 值访问器，返回数组元素的d[0]，即 60.8、58.4......
            });
          // 循环次数为节点的个数
          for (let i = 0; i < _this.radarData.length; i++) {
            let tmpLine = [];
            tmpLine.push([_this.radarData[i][6].value]);
            pieLinedate.push(pieLine(tmpLine));
          }
          // 定义线性颜色比例尺
          let colorScale = d3
            .scaleLog()
            .domain([10, 2000]) // 通常连续比例尺中的domain只包含两个值，但如果指定多个值时就会生成一个分位数的比例尺，例如创建一个分位数的颜色比例尺
            .range(["#ffffff", "#d85515"]);
          //添加对应数目的弧组，即<g>元素
          for (let i = 0; i < _this.radarData.length; i++) {
            var arcs = d3
              .select(_this.radarG._groups[0][i])
              .append("g")
              .attr("class", "pie")
              .selectAll("g")
              .data(pieLinedate[i]) //绑定转换后的数据piedata
              .enter()
              .append("g")
              .append("path")
              .attr("value", function(d) {
                return d.data[0];
              }) // 将代码行显示出来
              .attr("d", function(d) {
                return arc(d); // 弧生成器产生路径
              })
              .attr("fill", function(d) {
                // if (i == 10) return "#8fbc9a";
                if (_this.radarData[i][8].value != "file") return "#ffefae"; // 判断是文件夹
                return colorScale(d.data[0]); //设定弧的颜色
              })
              .style("pointer-events", "all")
              .on("mouseover", function(d, i) {
                // 显示出响应数据
                d3.select(
                  d3.select(this)._groups[0][0].parentNode.parentNode
                    .previousSibling
                )
                  .selectAll("text")
                  .attr("opacity", "1")
                  .attr("stroke", "black")
                  .attr("stroke-width", "0.3"); // 显示指标
                d3.select(this)
                  .attr("stroke", d3.select(this).attr("fill")) // 被选中的扇区添加边框
                  .attr("stroke-width", "1");
                // let newX = d3.event.pageX + 10;
                // let newY = d3.event.pageY + 10;
                // _this.tooltip
                //   .attr("x", newX)
                //   .attr("y", newY)
                //   .text("ncloc: " + d.data[0])
                //   .transition()
                //   .duration(200)
                //   .style("opacity", 1);
              })
              .on("mouseout", function() {
                d3.select(
                  d3.select(this)._groups[0][0].parentNode.parentNode
                    .previousSibling
                )
                  .selectAll("text")
                  .attr("opacity", "0");
                d3.select(this).attr("stroke-width", "0");
                // _this.tooltip
                //   .transition()
                //   .duration(200)
                //   .style("opacity", 1);
              });
          }
        }
        drawPie();
        groups
          .exit()
          .attr(
            "transform-origin",
            () =>
              _this.targetNode.y * Math.cos(_this.targetNode.x - Math.PI / 2) +
              " " +
              _this.targetNode.y * Math.sin(_this.targetNode.x - Math.PI / 2)
          ) //子树逐渐缩小到新位置
          .transition()
          .duration(_this.animateDuration)
          .attr("transform", "scale(0.01)")
          .remove();
      }
      /* ----------------------------渲染文本标签------------------------  */
      function renderText() {
        d3.selectAll(".text").remove();
        const groups = d3.selectAll(".g");
        groups
          .append("text")
          .attr("x", 0)
          .attr("y", 0)
          .attr("class", "text")
          .attr("text-anchor", "middle")
          .attr("dy", function(d) {
            let angle = ((180 * d.x) / Math.PI) % 360;
            if (angle > 90 && angle < 270) {
              return 30;
            }
            return -35;
          })
          .attr("font-size", "12px")
          .text(d => {
            return d.data.title;
          })
          .attr("opacity", function(d) {
            if (d.children == null) return 0; // 叶子节点的名字
            return 0;
          })
          .attr("transform", function(d) {
            let angle = ((180 * d.x) / Math.PI) % 360;
            if (angle > 90 && angle < 270) {
              angle = angle + 180;
            }
            const rotate =
              d.depth === 0 ? "rotate(0)" : "rotate(" + angle + ")";
            return rotate;
          });
      }
      /* ----------------------------渲染连线------------------------  */
      function renderLines() {
        let link = d3.select(".links");
        if (link.empty()) {
          link = d3
            .select(".body")
            .insert("g", ".groups")
            .attr("class", "links")
            .attr(
              "transform",
              "translate(" + _this.width / 2 + "," + _this.height / 2 + ")"
            );
        }

        const links = link.selectAll(".link").data(
          root.links().map(item => {
            item.id = item.source.id + "-" + item.target.id; // 为链接添加id
            return item;
          }),
          d => d.id
        );

        links
          .enter()
          .append("path")
          .attr("class", "link")
          .attr("fill", "none")
          .attr("stroke", _this.lineStroke)
          .attr(
            "transform-origin",
            () =>
              _this.oldY * Math.cos(_this.oldX - Math.PI / 2) +
              " " +
              _this.oldY * Math.sin(_this.oldX - Math.PI / 2)
          )
          .attr("transform", "scale(0.01)")
          .merge(links)
          .transition()
          .duration(_this.animateDuration)
          .attr("transform", "scale(1)")
          .attr(
            "d",
            d3
              .linkRadial()
              .angle(d => d.x)
              .radius(d => d.y)
          );

        links
          .exit()
          .attr(
            "transform-origin",
            () =>
              _this.targetNode.y * Math.cos(_this.targetNode.x - Math.PI / 2) +
              " " +
              _this.targetNode.y * Math.sin(_this.targetNode.x - Math.PI / 2)
          ) //子树逐渐缩小到新位置
          .transition()
          .duration(_this.animateDuration)
          .attr("transform", "scale(0.01)")
          .remove();
      }

      /* ----------------------------绑定鼠标交互事件------------------------  */
      function addMouseOn() {
        d3.selectAll(".g").on("click", function(d) {
          let fileDir = d3.select(this)._groups[0][0].classList[1]; // 获取当前选中的文件/文件夹的名称 test  #1.0.7
          if (fileDir.indexOf(".") != -1) {
            // 有 .  不是文件夹
            if (fileDir.indexOf("#") == -1) {
              // 没有 # 不是版本号
              _this.$store.state.filenameDir = fileDir; // 获取当前选中的文件
              console.log(_this.$store.state.filenameDir)
            }
          }
          let th = d3.select(this)._groups[0][0].__data__;
          toggle(th); // 传递的d 不是原来的d，需要通过this获取
          generateTree(root);
          renderNode();
          renderLines();
          renderText();
          addMouseOn();

          if (d.data.value == "dir") {
            // 是一个文件夹并且是折叠
            let pathObj = d3.select(this)._groups[0][0].firstChild.lastChild
              .firstChild.childNodes[0];
            let ChilLength = 0;
            try {
              ChilLength = d.children.length;
            } catch (err) {
              ChilLength = 0;
            }
            if (ChilLength == 0) {
              d3.select(pathObj).attr("fill", "#8fbc9a");
            } else {
              d3.select(pathObj).attr("fill", "#ffefae");
            }
          }
        });

        function toggle(d) {
          _this.first = true; // 确定是否为第一次点击
          if (d.children) {
            d._children = d.children;
            d.children = null;
          } else {
            d.children = d._children;
            d._children = null;
          }
          _this.oldX = d.x; //点击位置x坐标
          _this.oldY = d.y; //点击位置y坐标
          _this.targetNode = d; //被点击的节点，该节点的x和y坐标随后将被更新
        }
      }

      /* ----------------------------调用绘制图形的各个函数--------------------  */
      function render() {
        renderNode(); // 绘制节点
        renderText(); // 绘制节点文本
        renderLines(); // 绘制连接线
        addMouseOn(); // 鼠标的交互事件
      }
      function renderChart() {
        if(_this.svg == ''){
          _this.svg = d3
            .select("#box")
            .append("svg")
            .attr("width", 800)
            .attr("height", 440);

        _this.svg
          .append("defs")
          .append("clipPath")
          .attr("id", "clip")
          .append("rect")
          .attr("width", 520)
          .attr("height", 320)
          .attr("x", 10)
          .attr("y", 10);

        _this.svg
          .append("g")
          .attr("class", "body")
          .attr("id", _this.$store.state.singleVersion)
          .attr("transform", "translate(" + 50 + "," + 70 + ")");
        }
        // .attr("clip-path", "url(#clip)");   // 貌似没有用处  defs定义经常需要重复使用的元素

        //添加提示框
        // _this.tooltip = _this.svg
        //   .append("text")
        //   .attr("class", "tooltip")
        //   .style("opacity", 0);
        render();
      }
      renderChart();
    },


    // 按钮的点击事件
    showFilename(){
        let filenameG = d3.selectAll(".text");   // 选择所有文件名
        if(this.btnClick == 0){
        filenameG
          .each(function(d) {
            d3.select(this).attr('opacity', function(d){
            if (d.children == null) return 1; // 叶子节点的名字
            return 0;
            })
          });
          this.btnClick = 1
        }else{
          filenameG
          .each(function(d) {
            d3.select(this).attr('opacity', function(d){
            if (d.children == null) return 0; // 叶子节点的名字
            return 0;
            })
          });
          this.btnClick = 0
        }
    }
  }
};
</script>

<style>
.tooltipHtml {
  /* 这个设置没有用处 */
  position: absolute;
  width: auto;
  height: auto;
  background: #84b6d1;
  /* border :1px solid #ccc; */
  border-radius: 5px;
}

.singleButton {
  /* 按钮美化 */
  width: auto;
  height: 20px;
  margin-left: 10px;
  margin-top: 10px;
  border-width: 0px; /* 边框宽度 */
  border-radius: 3px; 
  background:#84b6d1; /* 背景颜色 */
  cursor: pointer; /* 鼠标移入按钮范围时出现手势 */
  outline: none; /* 不显示轮廓线 */
  font-family: Microsoft YaHei; /* 设置字体 */
  color: white; /* 字体颜色 */
  /* font-size: 17px; 字体大小 */
}
.singleButton:hover {
  /* 鼠标移入按钮范围时改变颜色 */
  background: #5599ff;
}
</style>
