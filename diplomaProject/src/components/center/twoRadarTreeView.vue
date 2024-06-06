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
      <button type="button" class="twoButton" @click="showTwoFilename()">
        Show Filename!
      </button>
    </div>
    <div id="twoBox">
      <div id="box1" style="width:450px; float:left"></div>
      <div id="box2" style="width:450px; float:left"></div>
    </div>
  </div>
</template>

<script>
import * as d3 from "d3";

export default {
  name: "twoRadarTreeView",
  data() {
    return {
      mainData1: "",
      mainData2: "",
      margins: { top: 0, left: 50, bottom: 0, right: 50 },
      textColor: "black",
      title: "径向树图",
      hoverColor: "#ff7e00",
      animateDuration: 1000,
      pointSize: 5,
      pointFill: "#c8b0e4",
      pointStroke: "transparent",
      lineStroke: "gray",
      width: 400,
      height: 300,
      oldX1: 0,
      oldY1: 0,
      oldX2: 0,
      oldY2: 0,
      targetNode1: "",
      targetNode2: "",
      first1: "",
      first2: "",
      svg1: null,
      svg2: null,
      nodeId1: 0,
      nodeId2: 0,
      radarG1: "",
      radarG2: "",
      diameter: 160, // 树图的直径,
      radarData1: [],
      radarData2: [],
      bugMax: 0,
      code_smellMax: 0,
      vulnerabilityMax: 0,
      ccMax: 0,
      dlMax: 0,
      clMax: 0,
      versionNumber1: this.$store.state.twoVersion1,
      versionNumber2: this.$store.state.twoVersion2,
      groupsEnter1: "",
      groupsEnter2: "",
      tooltipHtmlTwo: null,
      btnTwoClick: 0
    };
  },
  methods: {
    initTwoRadarTree() {
      let vm = this;
      this.versionNumber1 = this.$store.state.twoVersion1;
      this.versionNumber2 = this.$store.state.twoVersion2;

      vm.$axios({
        method: "post",
        url: "/twoRadarTreeDt",
        data: {
          versionNumber1: this.versionNumber1,
          versionNumber2: this.versionNumber2
        }
      })
        .then(res => {
          vm.mainData1 = res.data[0];
          vm.mainData2 = res.data[1];
          vm.bugMax = res.data[2]["bugMax"];
          vm.code_smellMax = res.data[2]["code_smellMax"];
          vm.vulnerabilityMax = res.data[2]["vulnerabilityMax"];
          vm.ccMax = res.data[2]["ccMax"];
          vm.dlMax = res.data[2]["dlMax"];
          vm.clMax = res.data[2]["clMax"];
          console.log(
            vm.bugMax,
            vm.code_smellMax,
            vm.vulnerabilityMax,
            vm.ccMax,
            vm.dlMax,
            vm.clMax
          );
          vm.drawRadarTreeView1(vm.mainData1);
          vm.drawRadarTreeView2(vm.mainData2);

          // 创建悬浮提示框
          vm.tooltipHtmlTwo = d3.select(".tooltipHtmlTwo");
          console.log(vm.tooltipHtmlTwo);
          if (vm.tooltipHtmlTwo._groups[0][0] == null) {
            vm.tooltipHtmlTwo = d3
              .select("#twoBox")
              .append("div")
              .attr("class", "tooltipHtmlTwo")
              .style("opacity", 0);
          }
        })
        .catch(reason => {
          console.log(reason);
        });
    },

    drawRadarTreeView1(Maindata1) {
      var _this = this;
      const root1 = d3.hierarchy(Maindata1);
      const generateTree1 = d3
        .cluster()
        .nodeSize([10, 10])
        .separation((a, b) => (a.parent === b.parent ? 1 : 1))
        // .separation((a, b) => (a.parent === b.parent ? 1 : 3))
        .size([2 * Math.PI, _this.diameter]);
      generateTree1(root1);

      function renderNode() {
        let nodes1 = d3.select(".groups1");
        if (nodes1.empty()) {
          nodes1 = d3
            .select(".body1")
            .append("g")
            .attr("class", "groups1")
            .attr("transform", "translate(" + 520 / 2 + "," + 300 / 2 + ")");
        }

        const groups1 = nodes1
          .selectAll(".g1")
          .data(root1.descendants(), d => d.id || (d.id = ++_this.nodeId1));

        _this.groupsEnter1 = groups1
          .enter()
          .append("g")
          // .attr("class", d => "g1 " + d.data.title)
          .attr("class", function(d) {
            let classname;
            if (typeof d.data.fileDir != "undefined") {
              classname = "g1 " + d.data.fileDir;
            } else {
              classname = "g1 #" + d.data.title;
            }
            return classname;
          })
          .on("mouseover", function(d) {
            // 悬浮框
            let ddHtml = d3.select(this)._groups[0][0].__data__;
            var toolY = 0,
              toolX = 0;
            _this.tooltipHtmlTwo
              .html(d => {
                toolX =
                  d3.event.clientX - 400 < 250
                    ? d3.event.clientX - 400
                    : d3.event.clientX - 250;
                toolY =
                  d3.event.clientY - 300 > 930
                    ? d3.event.clientY - 300
                    : d3.event.clientY - 350;
                // console.log(toolX, toolY)

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
              );
            }
          })
          .on("mouseout", function(d) {
            _this.tooltipHtmlTwo.html("");
            _this.tooltipHtmlTwo.style("opacity", 0);
            if (d.children != null) {
              d3.select(d3.select(this)._groups[0][0].lastChild).attr(
                "opacity",
                0
              );
            }
          })
          .attr("transform", (d, i) => {
            // 用真实数据初始化雷达图的数据
            _this.radarData1[i] = [
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

            if (_this.first1)
              return (
                "translate(" +
                _this.oldY1 * Math.cos(_this.oldX1 - Math.PI / 2) +
                "," +
                _this.oldY1 * Math.sin(_this.oldX1 - Math.PI / 2) +
                ")"
              ); //首次渲染，子树从（0，0）点开始放缩，否则，从点击位置开始放缩
          });

        /////////////////////////雷达图初始数据//////////////////////////////////////
        var axi_circle_point_num = 6; //极坐标的点数
        var axi_circle_num = 4; //坐标画几个圈
        var axi_circle_step; //坐标轴的每一步长度
        if (_this.radarData1.length >= 25) {
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
        let bscale = d3 // bug 漏洞的比例尺
          .scaleLinear()
          .domain([0, _this.bugMax])
          .range([0, axi_circle_num * axi_circle_step]);
        let vscale = d3 // bug 漏洞的比例尺
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

        _this.radarG1 = _this.groupsEnter1
          .append("g") // 增加存放雷达图的g
          .attr("class", function(d, i) {
            return "radarG1-" + i;
          });

        // 更改的内容
        if (_this.radarData1.length > 25) {
          _this.radarG1
            .append("circle")
            .attr("cx", "0")
            .attr("cy", "0")
            .attr("r", "15")
            .attr("fill", "#fff");
        } else {
          _this.radarG1
            .append("circle")
            .attr("cx", "0")
            .attr("cy", "0")
            .attr("r", "20")
            .attr("fill", "#fff");
        }

        _this.groupsEnter1
          .merge(groups1)
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
        _this.radarG1
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
        _this.radarG1
          .append("g")
          .selectAll("circle")
          .data(angles) // 6个点
          .enter()
          .append("circle")
          .attr("class", function(d, i) {
            // 每个指标添加不同的类，便于区分和获取
            return "m-" + i + "-" + _this.radarData1[0][i].key;
          })
          .attr("value", function(d, i) {
            // 添加value属性，表示每一个指标的值
            let fileNUmber = d3
              .select(this.parentNode.parentNode)
              .attr("class")
              .split("-")[1]; // 表示不同的文件
            return _this.radarData1[fileNUmber][i].value;
          })
          .attr("cx", function(d, i) {
            var fileNUmber = d3
              .select(this.parentNode.parentNode)
              .attr("class")
              .split("-")[1]; // 表示不同的文件
            var x;
            if (_this.radarData1[fileNUmber][i].key == "code_smells")
              x = scale(_this.radarData1[fileNUmber][i].value) * Math.cos(d);
            // 代码异味的比例尺
            else if (
              _this.radarData1[fileNUmber][i].key == "cognitive_complexity"
            )
              x = ccscale(_this.radarData1[fileNUmber][i].value) * Math.cos(d);
            // 认知复杂度的比例尺
            else if (_this.radarData1[fileNUmber][i].key == "bugs") {
              x = bscale(_this.radarData1[fileNUmber][i].value) * Math.cos(d); // bug 漏洞的比例尺
            } else if (
              _this.radarData1[fileNUmber][i].key == "vulnerabilities"
            ) {
              x = vscale(_this.radarData1[fileNUmber][i].value) * Math.cos(d); // bug 漏洞的比例尺
            } else if (
              _this.radarData1[fileNUmber][i].key == "duplicated_lines_density"
            ) {
              x = dlscale(_this.radarData1[fileNUmber][i].value) * Math.cos(d); // 注释行 重复行密度的比例尺
            } else if (
              _this.radarData1[fileNUmber][i].key == "comment_lines_density"
            ) {
              x = clscale(_this.radarData1[fileNUmber][i].value) * Math.cos(d); // 注释行 重复行密度的比例尺
            }
            return x;
          })
          .attr("cy", function(d, i) {
            var fileNUmber = d3
              .select(this.parentNode.parentNode)
              .attr("class")
              .split("-")[1];
            var y;
            if (_this.radarData1[fileNUmber][i].key == "code_smells")
              y = scale(_this.radarData1[fileNUmber][i].value) * Math.sin(d);
            // 代码异味的比例尺
            else if (
              _this.radarData1[fileNUmber][i].key == "cognitive_complexity"
            )
              y = ccscale(_this.radarData1[fileNUmber][i].value) * Math.sin(d);
            // 认知复杂度的比例尺
            else if (_this.radarData1[fileNUmber][i].key == "bugs")
              y = bscale(_this.radarData1[fileNUmber][i].value) * Math.sin(d);
            // bug 漏洞的比例尺
            else if (_this.radarData1[fileNUmber][i].key == "vulnerabilities")
              y = vscale(_this.radarData1[fileNUmber][i].value) * Math.sin(d);
            // bug 漏洞的比例尺
            else if (
              _this.radarData1[fileNUmber][i].key == "duplicated_lines_density"
            ) {
              y = dlscale(_this.radarData1[fileNUmber][i].value) * Math.sin(d); // 注释行 重复行密度的比例尺
            } else if (
              _this.radarData1[fileNUmber][i].key == "comment_lines_density"
            ) {
              y = clscale(_this.radarData1[fileNUmber][i].value) * Math.sin(d); // 注释行 重复行密度的比例尺
            }
            return y;
          })
          .attr("r", 1)
          .attr("fill", "#CC333F")
          .style("pointer-events", "all");

        //绘制雷达图的线条及其填充区域，循环的次数为节点的数目，即文件的数目
        for (var k = 0; k < _this.radarG1._groups[0].length; k++) {
          // k表示文件的索引号
          let lin = d3
            .lineRadial()
            .curve(d3.curveLinearClosed)
            .angle(d => {
              return d;
            })
            .radius((d, i) => {
              var r;
              if (_this.radarData1[k][i].key == "code_smells")
                r = scale(_this.radarData1[k][i].value);
              // 代码异味的比例尺
              else if (_this.radarData1[k][i].key == "cognitive_complexity")
                r = ccscale(_this.radarData1[k][i].value);
              // 认知复杂度的比例尺
              else if (_this.radarData1[k][i].key == "bugs")
                r = bscale(_this.radarData1[k][i].value);
              // bug 漏洞的比例尺
              else if (_this.radarData1[k][i].key == "vulnerabilities")
                r = vscale(_this.radarData1[k][i].value);
              // bug 漏洞的比例尺
              else if (
                _this.radarData1[k][i].key == "duplicated_lines_density"
              ) {
                r = dlscale(_this.radarData1[k][i].value); // 注释行 重复行密度的比例尺
              } else if (
                _this.radarData1[k][i].key == "comment_lines_density"
              ) {
                r = clscale(_this.radarData1[k][i].value); // 注释行 重复行密度的比例尺
              }
              return r; // 需要返回第k个文件的第i个指标
            });
          d3.select(_this.radarG1._groups[0][k])
            .append("g")
            .attr("class", "edge1")
            .attr("transform", "rotate(90)")
            .append("path")
            .attr("d", lin(angles))
            .attr("stroke", "blue")
            .attr("stroke-width", 1)
            .attr("fill", "#EDC951")
            .style("opacity", "0.2")
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

          // 指标的名称
          let metricNameArr = [
            "bug",
            "code smell",
            "vulnerability",
            "dld",
            "cd",
            "cld"
          ];
          d3.select(_this.radarG1._groups[0][k])
            .append("g")
            // .attr("transform", "translate(" + margin.left + ',' + margin.top + ')')
            .selectAll("text")
            .data(angles)
            .enter()
            .append("text")
            .text(function(d, i) {
              return metricNameArr[i];
            })
            .attr("font-size", "10px")
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

        // 绘制外层的圆环
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
          for (let i = 0; i < _this.radarData1.length; i++) {
            let tmpLine = [];
            tmpLine.push([_this.radarData1[i][6].value]);
            pieLinedate.push(pieLine(tmpLine));
          }
          // 定义线性颜色比例尺
          let colorScale = d3
            .scaleLog()
            .domain([10, 2000]) // 通常连续比例尺中的domain只包含两个值，但如果指定多个值时就会生成一个分位数的比例尺，例如创建一个分位数的颜色比例尺
            .range(["#ffffff", "#d85515"]);
          //添加对应数目的弧组，即<g>元素
          for (let i = 0; i < _this.radarData1.length; i++) {
            var arcs = d3
              .select(_this.radarG1._groups[0][i])
              .append("g")
              .attr("class", "pie")
              .selectAll("g")
              .data(pieLinedate[i]) //绑定转换后的数据piedata
              .enter()
              .append("g")
              .append("path")
              .attr("d", function(d) {
                return arc(d); // 弧生成器产生路径
              })
              .attr("fill", function(d) {
                // if (i == 10) return "#8fbc9a";
                if (_this.radarData1[i][8].value != "file") return "#ffefae"; // 判断是文件夹
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
                  .attr("stroke-width", "0.3");
                d3.select(this)
                  .attr("stroke", d3.select(this).attr("fill")) // 被选中的扇区添加边框
                  .attr("stroke-width", "0");
              })
              .on("mouseout", function() {
                d3.select(
                  d3.select(this)._groups[0][0].parentNode.parentNode
                    .previousSibling
                )
                  .selectAll("text")
                  .attr("opacity", "0");
                d3.select(this).attr("stroke-width", "0");
              });
          }
        }
        drawPie();
        groups1
          .exit()
          .attr(
            "transform-origin",
            () =>
              _this.targetNode1.y *
                Math.cos(_this.targetNode1.x - Math.PI / 2) +
              " " +
              _this.targetNode1.y * Math.sin(_this.targetNode1.x - Math.PI / 2)
          ) //子树逐渐缩小到新位置
          .transition()
          .duration(_this.animateDuration)
          .attr("transform", "scale(0.01)")
          .remove();
      }
      /* ----------------------------渲染文本标签------------------------  */
      function renderText() {
        d3.selectAll(".text1").remove();
        const groups1 = d3.selectAll(".g1"); // 展示没有用到
        groups1
          .append("text")
          .attr("x", 0)
          .attr("y", 0)
          .attr("class", "text1")
          .attr("text-anchor", "middle")
          .attr("dx", 0)
          .attr("dy", function(d) {
            let angle = ((180 * d.x) / Math.PI) % 360;
            if (angle > 90 && angle < 270) {
              return 30;
            }
            return -35;
          })
          .attr("opacity", 1)
          .attr("font-size", "13px")
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
        let link1 = d3.select(".links1");
        if (link1.empty()) {
          link1 = d3
            .select(".body1")
            .insert("g", ".groups1")
            .attr("class", "links1")
            .attr("transform", "translate(" + 520 / 2 + "," + 300 / 2 + ")");
        }

        const links1 = link1.selectAll(".link1").data(
          root1.links().map(item => {
            item.id = item.source.id + "-" + item.target.id; // 为链接添加id
            return item;
          }),
          d => d.id
        );

        links1
          .enter()
          .append("path")
          .attr("class", "link1")
          .attr("fill", "none")
          .attr("stroke", _this.lineStroke)
          .attr(
            "transform-origin",
            () =>
              _this.oldY1 * Math.cos(_this.oldX1 - Math.PI / 2) +
              " " +
              _this.oldY1 * Math.sin(_this.oldX1 - Math.PI / 2)
          )
          .attr("transform", "scale(0.01)")
          .merge(links1)
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

        links1
          .exit()
          .attr(
            "transform-origin",
            () =>
              _this.targetNode1.y *
                Math.cos(_this.targetNode1.x - Math.PI / 2) +
              " " +
              _this.targetNode1.y * Math.sin(_this.targetNode1.x - Math.PI / 2)
          ) //子树逐渐缩小到新位置
          .transition()
          .duration(_this.animateDuration)
          .attr("transform", "scale(0.01)")
          .remove();
      }

      /* ----------------------------绑定鼠标交互事件------------------------  */
      function addMouseOn() {
        d3.selectAll(".g1").on("click", function(d) {
          let fileDir = d3.select(this)._groups[0][0].classList[1]; // 获取当前选中的文件/文件夹的名称
          if (fileDir.indexOf(".") != -1) {
            if (fileDir.indexOf("#") == -1) {
              _this.$store.state.issuesVersion = _this.$store.state.twoVersion1.split(
                "--"
              )[1];
              _this.$store.state.filenameDir = fileDir; // 获取当前选中的文件
            }
          }

          let th = d3.select(this)._groups[0][0].__data__;
          toggle(th); // 传递的d 不是原来的d，需要通过this获取
          generateTree1(root1);
          renderNode();
          renderLines();
          renderText();
          addMouseOn();
          // 动态感改变文件夹节点的颜色
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
          _this.first1 = true; // 确定是否为第一次点击
          if (d.children) {
            d._children = d.children;
            d.children = null;
          } else {
            d.children = d._children;
            d._children = null;
          }
          _this.oldX1 = d.x; //点击位置x坐标
          _this.oldY1 = d.y; //点击位置y坐标
          _this.targetNode1 = d; //被点击的节点，该节点的x和y坐标随后将被更新
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
        if (_this.svg1 == null) {
          _this.svg1 = d3
            .select("#box1")
            .append("svg")
            .attr("width", 450)
            .attr("height", 440);

          _this.svg1
            .append("g")
            .attr("class", "body1")
            .attr("id", _this.versionNumber1)
            .attr("transform", "translate(" + -30 + "," + 65 + ")");
          render();
        }
      }
      renderChart();
    },
    // 绘制第二个雷达图
    drawRadarTreeView2(Maindata2) {
      var _this = this;
      const root2 = d3.hierarchy(Maindata2);
      const generateTree2 = d3
        .cluster()
        .nodeSize([10, 10])
        .separation((a, b) => (a.parent === b.parent ? 1 : 1))
        // .separation((a, b) => (a.parent === b.parent ? 1 : 3))
        .size([2 * Math.PI, _this.diameter]);
      generateTree2(root2);

      function renderNode() {
        let nodes2 = d3.select(".groups2");
        if (nodes2.empty()) {
          nodes2 = d3
            .select(".body2")
            .append("g")
            .attr("class", "groups2")
            .attr("transform", "translate(" + 520 / 2 + "," + 300 / 2 + ")");
        }

        const groups2 = nodes2
          .selectAll(".g2")
          .data(root2.descendants(), d => d.id || (d.id = ++_this.nodeId2));

        _this.groupsEnter2 = groups2
          .enter()
          .append("g")
          .attr("class", function(d) {
            let classname;
            if (typeof d.data.fileDir != "undefined") {
              classname = "g2 " + d.data.fileDir;
            } else {
              classname = "g2 #" + d.data.title;
            }
            return classname;
          })
          .on("mouseover", function(d) {
            // 悬浮框
            let ddHtml = d3.select(this)._groups[0][0].__data__;
            var toolY = 0,
              toolX = 0;
            _this.tooltipHtmlTwo
              .html(d => {
                toolX =
                  d3.event.clientX - 400 > 1330 ? 1330 : d3.event.clientX - 350;
                toolY =
                  d3.event.clientY - 300 > 930 ? 930 : d3.event.clientY - 300;
                let filename = ddHtml.data.title;
                let ncloc = ddHtml.data.metrics.lines
                let cc = ddHtml.data.metrics.cognitive_complexity;
                let cld = ddHtml.data.metrics.comment_lines_density;
                let bug = ddHtml.data.metrics.bugs;
                let code_smell = ddHtml.data.metrics.code_smells;
                let vulnerability = ddHtml.data.metrics.vulnerabilities;
                let dld = ddHtml.data.metrics.duplicated_lines_density;
                let str =
                  filename +
                  "<br/>" +
                  "ncloc: " +
                  ncloc +
                  "<br/>" +
                  "cognitive_complexity: " +
                  cc +
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
              );
            }
          })
          .on("mouseout", function(d) {
            _this.tooltipHtmlTwo.html("");
            _this.tooltipHtmlTwo.style("opacity", 0);
            if (d.children != null) {
              d3.select(d3.select(this)._groups[0][0].lastChild).attr(
                "opacity",
                1
              );
            }
          })
          .attr("transform", (d, i) => {
            // 用真实数据初始化雷达图的数据
            _this.radarData2[i] = [
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
            if (_this.first2)
              return (
                "translate(" +
                _this.oldY2 * Math.cos(_this.oldX2 - Math.PI / 2) +
                "," +
                _this.oldY2 * Math.sin(_this.oldX2 - Math.PI / 2) +
                ")"
              ); //首次渲染，子树从（0，0）点开始放缩，否则，从点击位置开始放缩
          });

        /////////////////////////雷达图初始数据//////////////////////////////////////
        var axi_circle_point_num = 6; //极坐标的点数
        var axi_circle_num = 4; //坐标画几个圈
        var axi_circle_step; //坐标轴的每一步长度
        if (_this.radarData2.length >= 25) {
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
        let bscale = d3 // bug 漏洞的比例尺
          .scaleLinear()
          .domain([0, _this.bugMax])
          .range([0, axi_circle_num * axi_circle_step]);
        let vscale = d3 // bug 漏洞的比例尺
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

        _this.radarG2 = _this.groupsEnter2
          .append("g") // 增加存放雷达图的g
          .attr("class", function(d, i) {
            return "radarG2-" + i;
          });

        // 更改的内容：设置背景颜色
        if (_this.radarData2.length > 25) {
          _this.radarG2
            .append("circle")
            .attr("cx", "0")
            .attr("cy", "0")
            .attr("r", "15")
            .attr("fill", "#fff");
        } else {
          _this.radarG2
            .append("circle")
            .attr("cx", "0")
            .attr("cy", "0")
            .attr("r", "20")
            .attr("fill", "#fff");
        }

        _this.groupsEnter2
          .merge(groups2)
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
        _this.radarG2
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
        _this.radarG2
          .append("g")
          .selectAll("circle")
          .data(angles) // 6个点
          .enter()
          .append("circle")
          .attr("class", function(d, i) {
            // 每个指标添加不同的类，便于区分和获取
            return "m-" + i + "-" + _this.radarData2[0][i].key;
          })
          .attr("value", function(d, i) {
            // 添加value属性，表示每一个指标的值
            let fileNUmber = d3
              .select(this.parentNode.parentNode)
              .attr("class")
              .split("-")[1]; // 表示不同的文件
            return _this.radarData2[fileNUmber][i].value;
          })
          .attr("cx", function(d, i) {
            var fileNUmber = d3
              .select(this.parentNode.parentNode)
              .attr("class")
              .split("-")[1]; // 表示不同的文件
            var x;
            if (_this.radarData2[fileNUmber][i].key == "code_smells")
              x = scale(_this.radarData2[fileNUmber][i].value) * Math.cos(d);
            // 代码异味的比例尺
            else if (
              _this.radarData2[fileNUmber][i].key == "cognitive_complexity"
            )
              x = ccscale(_this.radarData2[fileNUmber][i].value) * Math.cos(d);
            // 认知复杂度的比例尺
            else if (_this.radarData2[fileNUmber][i].key == "bugs") {
              x = bscale(_this.radarData2[fileNUmber][i].value) * Math.cos(d); // bug 漏洞的比例尺
            } else if (
              _this.radarData2[fileNUmber][i].key == "vulnerabilities"
            ) {
              x = vscale(_this.radarData2[fileNUmber][i].value) * Math.cos(d); // bug 漏洞的比例尺
            } else if (
              _this.radarData2[fileNUmber][i].key == "duplicated_lines_density"
            ) {
              x = dlscale(_this.radarData2[fileNUmber][i].value) * Math.cos(d); // 注释行 重复行密度的比例尺
            } else if (
              _this.radarData2[fileNUmber][i].key == "comment_lines_density"
            ) {
              x = clscale(_this.radarData2[fileNUmber][i].value) * Math.cos(d); // 注释行 重复行密度的比例尺
            }
            return x;
          })
          .attr("cy", function(d, i) {
            var fileNUmber = d3
              .select(this.parentNode.parentNode)
              .attr("class")
              .split("-")[1];
            var y;
            if (_this.radarData2[fileNUmber][i].key == "code_smells")
              y = scale(_this.radarData2[fileNUmber][i].value) * Math.sin(d);
            // 代码异味的比例尺
            else if (
              _this.radarData2[fileNUmber][i].key == "cognitive_complexity"
            )
              y = ccscale(_this.radarData2[fileNUmber][i].value) * Math.sin(d);
            // 认知复杂度的比例尺
            else if (_this.radarData2[fileNUmber][i].key == "bugs")
              y = bscale(_this.radarData2[fileNUmber][i].value) * Math.sin(d);
            // bug 漏洞的比例尺
            else if (_this.radarData2[fileNUmber][i].key == "vulnerabilities")
              y = vscale(_this.radarData2[fileNUmber][i].value) * Math.sin(d);
            // bug 漏洞的比例尺
            else if (
              _this.radarData2[fileNUmber][i].key == "duplicated_lines_density"
            ) {
              y = dlscale(_this.radarData2[fileNUmber][i].value) * Math.sin(d); // 注释行 重复行密度的比例尺
            } else if (
              _this.radarData2[fileNUmber][i].key == "comment_lines_density"
            ) {
              y = clscale(_this.radarData2[fileNUmber][i].value) * Math.sin(d); // 注释行 重复行密度的比例尺
            }
            return y;
          })
          .attr("r", 1)
          .attr("fill", "#CC333F")
          .style("pointer-events", "all");

        //绘制雷达图的线条及其填充区域，循环的次数为节点的数目，即文件的数目
        for (var k = 0; k < _this.radarG2._groups[0].length; k++) {
          // k表示文件的索引号
          let lin = d3
            .lineRadial()
            .curve(d3.curveLinearClosed)
            .angle(d => {
              return d;
            })
            .radius((d, i) => {
              var r;
              if (_this.radarData2[k][i].key == "code_smells")
                r = scale(_this.radarData2[k][i].value);
              // 代码异味的比例尺
              else if (_this.radarData2[k][i].key == "cognitive_complexity")
                r = ccscale(_this.radarData2[k][i].value);
              // 认知复杂度的比例尺
              else if (_this.radarData2[k][i].key == "bugs")
                r = bscale(_this.radarData2[k][i].value);
              // bug 漏洞的比例尺
              else if (_this.radarData2[k][i].key == "vulnerabilities")
                r = vscale(_this.radarData2[k][i].value);
              // bug 漏洞的比例尺
              else if (
                _this.radarData2[k][i].key == "duplicated_lines_density"
              ) {
                r = dlscale(_this.radarData2[k][i].value); // 注释行 重复行密度的比例尺
              } else if (
                _this.radarData2[k][i].key == "comment_lines_density"
              ) {
                r = clscale(_this.radarData2[k][i].value); // 注释行 重复行密度的比例尺
              }
              return r; // 需要返回第k个文件的第i个指标
            });
          d3.select(_this.radarG2._groups[0][k])
            .append("g")
            .attr("class", "edge2")
            .attr("transform", "rotate(90)")
            .append("path")
            .attr("d", lin(angles))
            .attr("stroke", "blue")
            .attr("stroke-width", 1)
            .attr("fill", "#EDC951")
            .style("opacity", "0.2")
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
                .style("opacity", "0.2");
            });

          // 指标的名称
          let metricNameArr = [
            "bug",
            "code smell",
            "vulnerability",
            "dld",
            "cd",
            "cld"
          ];
          d3.select(_this.radarG2._groups[0][k])
            .append("g")
            .selectAll("text")
            .data(angles)
            .enter()
            .append("text")
            .text(function(d, i) {
              return metricNameArr[i];
            })
            .attr("font-size", "10px")
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

        // 绘制外层的圆环
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
          for (let i = 0; i < _this.radarData2.length; i++) {
            let tmpLine = [];
            tmpLine.push([_this.radarData2[i][6].value]);
            pieLinedate.push(pieLine(tmpLine));
          }
          // 定义线性颜色比例尺
          let colorScale = d3
            .scaleLog()
            .domain([10, 2000]) // 通常连续比例尺中的domain只包含两个值，但如果指定多个值时就会生成一个分位数的比例尺，例如创建一个分位数的颜色比例尺
            .range(["#ffffff", "#d85515"]);
          //添加对应数目的弧组，即<g>元素
          for (let i = 0; i < _this.radarData2.length; i++) {
            var arcs = d3
              .select(_this.radarG2._groups[0][i])
              .append("g")
              .attr("class", "pie")
              .selectAll("g")
              .data(pieLinedate[i]) //绑定转换后的数据piedata
              .enter()
              .append("g")
              .append("path")
              .attr("d", function(d) {
                return arc(d); // 弧生成器产生路径
              })
              .attr("fill", function(d) {
                // if (i == 10) return "#8fbc9a";
                if (_this.radarData2[i][8].value != "file") return "#ffefae"; // 判断是文件夹
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
                  .attr("stroke-width", "0.3");
                d3.select(this)
                  .attr("stroke", d3.select(this).attr("fill")) // 被选中的扇区添加边框
                  .attr("stroke-width", "0");
              })
              .on("mouseout", function() {
                d3.select(
                  d3.select(this)._groups[0][0].parentNode.parentNode
                    .previousSibling
                )
                  .selectAll("text")
                  .attr("opacity", "0");
                d3.select(this).attr("stroke-width", "0");
              });
          }
        }
        drawPie();
        groups2
          .exit()
          .attr(
            "transform-origin",
            () =>
              _this.targetNode2.y *
                Math.cos(_this.targetNode2.x - Math.PI / 2) +
              " " +
              _this.targetNode2.y * Math.sin(_this.targetNode2.x - Math.PI / 2)
          ) //子树逐渐缩小到新位置
          .transition()
          .duration(_this.animateDuration)
          .attr("transform", "scale(0.01)")
          .remove();
      }
      /* ----------------------------渲染文本标签------------------------  */
      function renderText() {
        d3.selectAll(".text2").remove();
        const groups2 = d3.selectAll(".g2"); // 展示没有用到
        groups2
          .append("text")
          .attr("x", 0)
          .attr("y", 0)
          .attr("class", "text2")
          .attr("text-anchor", "middle")
          .attr("dx", 0)
          .attr("dy", function(d) {
            let angle = ((180 * d.x) / Math.PI) % 360;
            if (angle > 90 && angle < 270) {
              return 30;
            }
            return -35;
          })
          .attr("opacity", 1)
          .text(d => {
            return d.data.title;
          })
          .attr("opacity", function(d) {
            if (d.children == null) return 0; // 叶子节点的名字
            return 0;
          })
          .attr("font-size", "13px")
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
        let link2 = d3.select(".links2");
        if (link2.empty()) {
          link2 = d3
            .select(".body2")
            .insert("g", ".groups2")
            .attr("class", "links2")
            .attr("transform", "translate(" + 520 / 2 + "," + 300 / 2 + ")");
        }

        const links2 = link2.selectAll(".link2").data(
          root2.links().map(item => {
            item.id = item.source.id + "-" + item.target.id; // 为链接添加id
            return item;
          }),
          d => d.id
        );

        links2
          .enter()
          .append("path")
          .attr("class", "link2")
          .attr("fill", "none")
          .attr("stroke", _this.lineStroke)
          .attr(
            "transform-origin",
            () =>
              _this.oldY2 * Math.cos(_this.oldX2 - Math.PI / 2) +
              " " +
              _this.oldY2 * Math.sin(_this.oldX2 - Math.PI / 2)
          )
          .attr("transform", "scale(0.01)")
          .merge(links2)
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

        links2
          .exit()
          .attr(
            "transform-origin",
            () =>
              _this.targetNode2.y *
                Math.cos(_this.targetNode2.x - Math.PI / 2) +
              " " +
              _this.targetNode2.y * Math.sin(_this.targetNode2.x - Math.PI / 2)
          ) //子树逐渐缩小到新位置
          .transition()
          .duration(_this.animateDuration)
          .attr("transform", "scale(0.01)")
          .remove();
      }

      /* ----------------------------绑定鼠标交互事件------------------------  */
      function addMouseOn() {
        // 点击事件
        d3.selectAll(".g2").on("click", function(d) {
          let fileDir = d3.select(this)._groups[0][0].classList[1]; // 获取当前选中的文件/文件夹的名称
          if (fileDir.indexOf(".") != -1) {
            if (fileDir.indexOf("#") == -1) {
              _this.$store.state.issuesVersion = _this.$store.state.twoVersion2.split(
                "--"
              )[1];
              _this.$store.state.filenameDir = fileDir; // 获取当前选中的文件
            }
          }
          // 悬浮事件

          let th = d3.select(this)._groups[0][0].__data__;
          toggle(th); // 传递的d 不是原来的d，需要通过this获取
          generateTree2(root2);
          renderNode();
          renderLines();
          renderText();
          addMouseOn();
          // 改变文件夹的颜色
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
          _this.first2 = true; // 确定是否为第一次点击
          if (d.children) {
            d._children = d.children;
            d.children = null;
          } else {
            d.children = d._children;
            d._children = null;
          }
          _this.oldX2 = d.x; //点击位置x坐标
          _this.oldY2 = d.y; //点击位置y坐标
          _this.targetNode2 = d; //被点击的节点，该节点的x和y坐标随后将被更新
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
        console.log(_this.svg2 == null);
        if (_this.svg2 == null) {
          _this.svg2 = d3
            .select("#box2")
            .append("svg")
            .attr("width", 450)
            .attr("height", 440);

          _this.svg2
            .append("g")
            .attr("class", "body2")
            .attr("id", _this.versionNumber1)
            .attr("transform", "translate(" + -30 + "," + 65 + ")");

          render();
        }
      }
      renderChart();
    },

    // 按钮的点击事件
    showTwoFilename() {
      let filenameG = d3.selectAll(".text1, .text2"); // 选择所有文件名
      if (this.btnTwoClick == 0) {
        filenameG.each(function(d) {
          d3.select(this).attr("opacity", function(d) {
            if (d.children == null) return 1; // 叶子节点的名字
            return 0;
          });
        });
        this.btnTwoClick = 1;
      } else {
        filenameG.each(function(d) {
          d3.select(this).attr("opacity", function(d) {
            if (d.children == null) return 0; // 叶子节点的名字
            return 0;
          });
        });
        this.btnTwoClick = 0;
      }
    }
  }
};
</script>

<style>
.twoButton {
  /* 按钮美化 */
  width: auto;
  height: 20px;
  margin-left: 10px;
  margin-top: 10px;
  border-width: 0px; /* 边框宽度 */
  border-radius: 3px;
  background: #84b6d1; /* 背景颜色 */
  cursor: pointer; /* 鼠标移入按钮范围时出现手势 */
  outline: none; /* 不显示轮廓线 */
  font-family: Microsoft YaHei; /* 设置字体 */
  color: white; /* 字体颜色 */
  /* font-size: 17px; 字体大小 */
}
.twoButton:hover {
  /* 鼠标移入按钮范围时改变颜色 */
  background: #5599ff;
}
</style>
