<!--
 * @Descripttion: 
 * @version: 
 * @Author: Yolanda
 * @Date: 2021-04-09 18:57:13
 * @LastEditors: Yolanda
 * @LastEditTime: 2021-04-15 19:49:21
-->
<template>
  <div style="margin-left: 10px;display: flex; ">
    <div id="legendDefine" style="height: 400px; width:140px;">
      <h6 style="margin-block-start: 0; margin-block-end: 0;">QUALITY VIEW</h6>
    </div>
    <div id="main-view"></div>
  </div>
</template>

<script>
import * as d3 from "d3";

export default {
  name: "mainView",
  data() {
    return {
      mainData: []
    };
  },
  computed:{
    isChangeShowCommitAndPie(){
      return this.$store.state.showCommitAndPie   // 返回显示commit和pie的flag
    }
  },
  watch:{
    isChangeShowCommitAndPie: function(){
      this.changeShowCommitAndPie()
      // this.drawLegend()
    }
  },
  mounted() {
    this.$axios({
      method: "get",
      url: "/mainDt"
    })
      .then(res => {
        this.mainData = res.data
        this.drawMainView()
        this.drawLegend()
      })
      .catch(reason => {
        console.log(reason);
      });
  },
  methods: {
    drawMainView() {
      var width = 960,
          height = 2400; // 设置画布的长 宽，宽度为文件数量*矩形宽度
      var metricSum = 3; // 评价指标的数量
      var margin = { top: 60, right: 200, bottom: 30, left: 160},
        barHeight = 20, //The height of the rectangle bar.
        barWidth = 730;
      var _this = this
      var i = 0,
        duration = 0,
        root;
      var versionName = [
        "V1-0-7",
        "V1-0-8",
        "V1-0-9",
        "V1-1-0",
        "V1-1-1",
        "V1-1-2",
        "V1-1-3",
        "V1-1-4",
        "V1-1-5",
        "V1-1-6",
        "V1-1-7",
        "V1-1-8",
        "V1-1-9",
        "V1-2-0",
        "V1-2-1",
        "V1-2-2",
        "V1-2-4",
        "V1-2-5",
        "V1-2-6",
        "V1-2-7",
        "V1-2-8",
        "V1-2-9",
        "V1-2-10",
        "V1-2-11",
        "V1-2-12",
        "Vgithub",
        "V1-2-3",
        "V1-2-13",
        "V1-2-14",
        "V1-2-15",
        "V1-2-16"
      ];
      var versionNumber = versionName.length; // 版本数目
      var versionGap = 700 / versionNumber;
      var piedatas = [];
      var metricName = ["code smell", "bug", "vulnerability"]; // 顺序不对应，未解？？
      /* 2. The main svg. */
      var svg = d3
        .select("#main-view")
        .append("svg")
        .attr("width", width) // svg的宽度： margin.left + margin.right)
        .style("height", height) // svg的高度
        .append("g")
        .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

      /* 3. 从文件夹中获取数据. */
        // 初始化饼图的数据, 115为项目的文件总数
        for (var i = 0; i < 115; i++) {
          piedatas[i] = [];
        }
        // 绘制图形
        root = d3.hierarchy(this.mainData); // Create a hierarchical layout
        root.x0 = 0;
        root.y0 = 0;
        
        update(root);

      /* 4. 绘制层次结构图，视图绘制的主要函数  */
      function update(source) {
        var nodes = root.descendants();
        var height = Math.max(
          500,
          nodes.length * barHeight + margin.top + margin.bottom
        );

        // 饼图的数据：bug, vulnerabilities,code_smells
        for (var i = 0; i < nodes.length; i++) {
          if (nodes[i].data.value == "dir") {
            for (let versionNum = 0; versionNum < 31; versionNum++)
              piedatas[i].push([0, 0, 0]);
          } else {
            for (let versionNum = 0;versionNum < nodes[i].data.bug.length;versionNum++) {
              let bugs = nodes[i].data.bug[versionNum].bug;
              let vulnerabilities =nodes[i].data.vulnerability[versionNum].vulnerability;
              let code_smells = nodes[i].data.code_smell[versionNum].code_smell;
              piedatas[i].push([bugs, vulnerabilities, code_smells]);
            } 
          }
        }

        d3.select("svg")
          .transition()
          .duration(duration)
          .attr("height", height);
        ///////////////////////////////////无用处
        d3.select(self.frameElement)
          .transition()
          .duration(duration)
          .style("height", height + "px");
        ///////////////////////////////////无用处

        var index = -1;
        root.eachBefore(function(n) {
          n.x = ++index * barHeight; // 节点的y坐标  设置节点之间的前后距离
          n.y = n.depth * 15; // 节点的x坐标
        });

        // 更新节点
        var node = svg.selectAll(".node").data(nodes, function(d, i) {
          return d.id || (d.id = ++i); // 1-37
        });

        var nodeEnter = node
          .enter()
          .append("g")
          .attr("class", "node")
          .style("opacity", 0);

        // 绘制文件名前面的符号
        console.log(nodeEnter)
        for(let i=0; i<nodeEnter._groups[0].length; i++){
          try{
            if(nodeEnter._groups[0][i].__data__.children != null){  // 如果有叶子几点 
            d3.select(nodeEnter._groups[0][i])
                      .append("path")
                      .attr("class", 'addFolder')
                      .attr("d", "M-109,-2 L-105,-2 L-107,2")
                      // .attr("d", "M-109,-3 L-107,-1 L-109,1")
                      .attr("stroke", "rgb(181, 181, 181)")
                      .attr("stroke-width", 1.5)
                      .attr("fill", "rgb(181, 181, 181)") 
            }
          }catch(e){

          }

        }
        // 绘制文件名
        nodeEnter
          .append("text")
          .attr("class", "filename")
          .attr('dx', -100)
          .text(function(d, i) {
            return d.data.name;
          })
          .style("fill", function(d) {
            if (d.data.value == "dir")
              // 只根据是否为文件夹来定义不同的颜色
              return "#de9c00";
            return "#000";
          })
          .style("font-size", function(d) {
            if (d.depth == "0") return "14px";
            else if (d.depth == "1") return "13px";
            else if (d.depth == "2") return "12px";
            else if (d.depth == "3") return "11px";
            else return "10px";
          }) 
          .style('text-anchor', 'start')
          .style('dominant-baseline', 'middle')
          .on('click', filenameClick)

        // 绘制包裹小矩形的外环大矩形，长矩形条
        var outerRect = nodeEnter
          .append("rect")
          .attr("x", function(d) {
            if (d.data.value == "file") {
              let startX = 52 - d.y;
              let gap = eval(d.data.created.split("--")[0]);
              return startX + versionGap * gap; // 只显示文件创建之后的历史
            } else if (d.data.value == "dir") {
              let startXf = 52 - d.y;
              let gapf = eval(d.data.created.split("--")[0]);
              return startXf + versionGap * gapf; // 只显示文件创建之后的历史
            }
            return 200;
          })
          .attr("y", function(d) {
            return -barHeight / 20;
          })
          .attr("height", 5)
          .attr("width", nodeWidth)
          .style("fill", color)
          .style('cursor', 'pointer')
          .style("fill-opacity", '1')
          .style("stroke-width", '0.5px')
          .on("click", click);

        // 定义饼图的数据
        var pieData = [];
        var node_location = []; // 存储外层大矩形节点的坐标
        var node_index = 0; // 节点索引，获取对应节点的坐标

        // 将commit数据绑定上去
        var nd = 0;
        var CommitCb = d3.rgb(50, 50, 50); //红色
        var CommitCa = d3.rgb(230, 220, 210); //绿色
        var compute = d3.interpolate(CommitCa, CommitCb); // 产生线性渐变色
        var linearCommit = d3
          .scaleLinear()
          .domain([0, 20])
          .range([0, 1]);
        for (var ck = 0; ck < nodes.length; ck++) {
          for (var cj = 0; cj < versionNumber; cj++) {
            d3.select(nodeEnter._groups[0][ck]) // ck表示文档的个数 0-36, cj表示文件的第几个版本
              .append("g")
              .attr("location", function(d, i) {
                node_location.push([d.y, d.x]); // 存储外层大矩形节点的坐标
                let x =
                  60 -
                  node_location[Math.floor(nd / metricSum)][0] +
                  versionGap * cj;
                return x;
              })
              .attr("name", "commit")
              .append("rect")
              .attr("class", "commitRect")
              .attr("x", d => {
                let x =
                  60 -
                  node_location[Math.floor(nd / metricSum)][0] +
                  versionGap * cj;
                nd = nd + 3;
                return x - 7;
              })
              .attr("y", -7)
              .attr("width", 14)
              .attr("height", 14)
              .attr("fill", function(d) {
                if (d.data.value == "dir" || d.data.commit[cj].commit == 0)
                  return "transparent";
                return compute(linearCommit(d.data.commit[cj].commit));
              })
              .attr("opacity", 1)
              .attr("value", d => {
                return d.data.value == "dir" ? 0 : d.data.commit[cj].commit;
              });
          }
        }

        /**************************添加饼图****************************************/
        //设置一个color的颜色比例尺，为了让不同的扇形呈现不同的颜色
        var colorScale = d3
          .scaleOrdinal()
          .domain(d3.range(piedatas.length))
          .range(d3.schemeCategory10);
        var pieColor = ["#ffc700", "#ca64ea", "#a3caeb"];

        // 新建一个饼图
        var pieGraph = d3.pie();
        // 将原始数据变成可以绘制饼状图的数据
        for (var k = 0; k < nodes.length; k++) {
          var prevBug = 0,
            prevVulnerability = 0,
            prevCode_smell = 0; // 用来存储上一个版本的各项指标的值，并初始化为0
          for (var j = 0; j < versionNumber; j++) {
            var innerRadius = 0; //内半径S
            var outerRadius = 6; //外半径
            var arc_generator = d3 // 新建一个弧形生成器
              .arc()
              .innerRadius(innerRadius)
              .outerRadius(outerRadius);
            var pieData = pieGraph(piedatas[k][j]); // 第k个文档的第j个版本
            d3.select(nodeEnter._groups[0][k]) // k表示文档的个数 0-36
              .append("g")
              .attr("location", function(d, i) {
                node_location.push([d.y, d.x]);
                var x = 60 - node_location[Math.floor(node_index / metricSum)][0] + versionGap * j;
                return x;
              })
              .attr("id", "g_" + versionName[j])
              .attr("class", "pieNode")
              .selectAll("g")
              .data(pieData)
              .enter()
              .append("g")
              .attr("class", "smallPie")
              .attr("transform", d => {
                var cx = 60 - node_location[Math.floor(node_index / metricSum)][0] + versionGap * j;
                var cy = 0;
                node_index = node_index + 1;
                return "translate(" + cx + "," + cy + ")"; //位置信息
              })
              .append("path")
              .attr("d", function(d) {
                return arc_generator(d); //往弧形生成器中出入数据
              })
              .attr("fill", function(d, i) {
                return pieColor[i]; //设置填充颜色
              })
              .attr("stroke", (d, i, w) => {
                var strokeColor = "transparent"; // 不变
                if (i == 0) {
                  if (prevBug < d.value)// 增加了
                    strokeColor = "#eb3c0f";
                  else if (prevBug > d.value && d.value != 0)// 减少了
                    strokeColor = "#46485f";
                  prevBug = d.value;
                } else if (i == 1) {
                  if (prevVulnerability < d.value)// 增加了
                    strokeColor = "#ff8f6b";
                  else if (prevVulnerability > d.value && d.value != 0){// 减少了
                    strokeColor = "#46485f";
                  }
                  prevVulnerability = d.value;
                } else {
                  if (prevCode_smell < d.value)// 增加了
                    strokeColor = "#e6a23c";
                  else if (prevCode_smell > d.value && d.value != 0){// 减少了
                    strokeColor = "#46485f";
                  }
                  prevCode_smell = d.value;
                }
                return strokeColor;
              })
              .attr("stroke-width", 1)
              .attr("opacity", "1")
              .attr("value", d => {
                return d.value;
              })
              .attr("name", d => {
                return metricName[d.index];
              })
              .on("mouseover", pieMouseOver)
              .on("mouseout", pieMouseOut)
              .on("click", pieClick);
          }
        }

        // /*********************在每一个版本上面添加版本号***********************************/
        for (var versionTitleNum = 0; versionTitleNum < versionNumber; versionTitleNum++
        ) {
          d3.select(nodeEnter._groups[0][0]) // 选中所有节点中的第一个节点
            .append("text")
            .text(versionName[versionTitleNum].replaceAll("-", "."))
            .attr("class", "versionName")
            .attr("location", function(d) {
              return 60 - d.x + versionGap * versionTitleNum;
            })
            .attr("id", versionName[versionTitleNum])
            .attr("x", d => {
              return 60 - d.x + versionGap * versionTitleNum;
            }) // 设置x值
            .attr("y", -13) // 设置y值
            .attr("transform", (d, i) => {
              var x = 50 - d.x + versionGap * versionTitleNum;
              return "rotate(-45, " + x + " " + -23 + ")"; // 让每个text旋转的起点为相应的x起点，而不是最左边的起始点
            })
            .style("color", "#b5b5b5")
            .style('font-size', '10px')
            .style('font-weight', 'bold')
            .style('text-anchor', 'middle')
            .on("click", versionNameClick)
            .on("mouseover", versionNameMouseOver)
            .on("mouseout", versionNameMouseOut);
        }

        // Transition nodes to their new position.
        nodeEnter
          .transition()
          .duration(duration)
          .attr("transform", function(d) {
            return "translate(" + d.y + "," + d.x + ")";
          })
          .style("opacity", 1);

        node
          .transition()
          .duration(duration)
          .attr("transform", function(d) {
            return "translate(" + d.y + "," + d.x + ")";
          })
          .style("opacity", 1)
          .select("rect")
          .style("fill", color);

        // Transition exiting nodes to the parent's new position.
        node
          .exit()
          .transition()
          .duration(duration)
          .attr("transform", function(d) {
            return "translate(" + source.y + "," + source.x + ")";
          })
          .style("opacity", 0)
          .remove();

        // Stash the old positions for transition.
        root.each(function(d) {
          d.x0 = d.x;
          d.y0 = d.y;
        });
      }

      /**  绘制滑动条    */
      var float_barG = d3
        .select("#float-bar")
        .append("svg")
        .attr("width", width - 250)
        .style("height", 20)
        .attr("transform", "translate(80,0)");
      var floatBar = float_barG.append("g");

      var drag_background = floatBar
        .append("rect") //添加滑动的背景条
        .attr("x", 30)
        .attr("y", 5)
        .attr("width", width - 300)
        .attr("height", 10)
        .attr("fill", "rgb(236, 236, 236)");

      var drag_bar = floatBar
        .append("rect") // 滑条
        .attr("x", 30)
        .attr("y", 5)
        .attr("id", "drag_bar")
        .attr("width", 25)
        .attr("height", 10)
        .attr("fill", "rgb(181, 181, 181)")

      var ArrowG = float_barG.append("g");
      var commitFlag = true;
      var metricFlag = true;
      var leftArrow = ArrowG.append("rect") // 左箭头
        .attr("x", 15)
        .attr("y", 5)
        .attr("width", 10)
        .attr("height", 10)
        .attr("fill", "rgb(236, 236, 236)")
        .on("click", function() {
          if (commitFlag == true) {
            d3.selectAll(".commitRect").attr("opacity", 0);
            commitFlag = false;
          } else {
            d3.selectAll(".commitRect").attr("opacity", 1);
            commitFlag = true;
          }
        });
      ArrowG.append("path")
        .attr("d", "M22,7 L19,10 L22,13")
        .attr("stroke", "rgb(181, 181, 181)")
        .attr("stroke-width", 1.5)
        .attr("fill", "transparent");

      var rightArrow = ArrowG.append("rect") // 右箭头
        .attr("x", 695)
        .attr("y", 5)
        .attr("width", 10)
        .attr("height", 10)
        .attr("fill", "rgb(236, 236, 236)")
        .on("click", function() {
          if (metricFlag == true) {
            d3.selectAll(".smallPie").attr("opacity", 0);
            metricFlag = false;
          } else {
            d3.selectAll(".smallPie").attr("opacity", 1);
            metricFlag = true;
          }
        });
      ArrowG.append("path")
        .attr("d", "M698,7 L701,10 L698,13")
        .attr("stroke", "rgb(181, 181, 181)")
        .attr("stroke-width", 1.5)
        .attr("fill", "transparent");

      /************************************************交互****************************************************/

      /* 5. Toggle children on click. */
      function click(d) {
        var dd = d3.select(this)._groups[0][0].__data__
        let curd = d3.select(this)._groups[0][0].parentNode.firstChild
        if (dd.children) {   
          dd._children = dd.children;
          dd.children = null;
        // 点击更新折叠标识符
          d3.select(curd).attr('d', "M-107,-4 L-104,-1 L-107,2")
        } else {
          dd.children = dd._children;
          dd._children = null;
        // 点击更新折叠标识符
          d3.select(curd).attr('d', "M-109,-2 L-105,-2 L-107,2")
        }
        update(dd);
      }

      /* 6. Define different color. */
      function color(d) {
        return d._children ? "#8fbc9a" : d.children ? "#ffefae" : "#e5e7e8"; // 折叠之后的颜色、文件夹的颜色、文件的颜色
      }
      // 确定外层大矩形的宽度
      function nodeWidth(d) {
        if (d.data.value == "file") {
          let startX = eval(d.data.created.split("--")[0]);
          let endX = eval(d.data.end.split("--")[0]);
          let gap = endX - startX + 1;
          return gap * versionGap - 8;
        } else if (d.data.value == "dir") {
          let startXf = eval(d.data.created.split("--")[0]);
          let endXf = eval(d.data.end.split("--")[0]);
          let gapf = endXf - startXf + 1;
          return gapf * versionGap - 8;
        }

        // return barWidth - d.y;   // 定义所有的矩形条的长度在同一个地方截止
      }
      // 确定外层大矩形的高度
      function nodeHeight(d) {
        return barHeight;
      }

      /*****************************交互设置******************************************/
      /* 函数用于生成小矩形的悬浮事件*/
      // 饼图悬浮提示框
      let tooltip = d3
        .select("#main-view")
        .append("div")
        .attr("class", "tooltip")
        .style("opacity", 0);
      // 饼图鼠标放上事件
      function pieMouseOver(d) {
        if (d.value != 0) {
          d3.select(this)
            // .attr("stroke", d3.select(this).attr("fill")) // 被选中的扇区添加边框
            .attr("stroke-width", "2");

          var _this = this;
          d3.selectAll(".smallPie")
            .filter(function(d, i) {
              return d3.select(this.children)._groups[0][0][0] != _this; // 没有被选中的节点的透明度降低
            })
            .attr("opacity", "0.1");

          var toolY = 0, toolX = 0
          tooltip
            .html(d => {
              toolX = eval(d3.select(d3.select(this)._groups[0][0].parentNode.parentNode).attr('location')) + 160
              toolY = eval(d3.select(d3.select(this)._groups[0][0].parentNode.parentNode.parentNode).attr('transform').split(',')[1].split(')')[0]) + 70
              let versionNumber = d3
                .select(this.parentNode.parentNode)
                .attr("id")
                .split("_")[1]
                .replaceAll("-", ".");
              let filename = d3.select(this.parentNode.parentNode.parentNode.firstChild).text();
              let str = filename + "<br/>" + versionNumber + "<br/>" + d3.select(this).attr("name") + ":" + d3.select(this).attr("value");
              return str;
            })
            .style("left", toolX + "px")
            .style("top", toolY + "px")
            .style("font-size", "12px")
            .style("opacity", 1)
            .style('position', 'absolute')
            .style('width', 'auto')
            .style('height', 'auto')
            .style('border-radius', '5px')
            .style('background', '#84b6d1')
        }
      }
      // 饼图鼠标移走事件
      function pieMouseOut(d) {
        let showPieFag = false
        for(let i= 0; i<_this.$store.state.showCommitAndPie.length; i++){
          if('show pie' == _this.$store.state.showCommitAndPie[i]){    // 显示pie
            showPieFag = true
          }
        }
        if (showPieFag == true && d.value != 0) {
          d3.select(this).attr("stroke-width", "1"); // 隐去边框

          d3.selectAll(".smallPie").attr("opacity", "1"); // 所有节点的透明度恢复到默认值
        }
        
        tooltip.style("opacity", 0);
      }
      // 饼图点击事件
      var pieClickFlag = false; // 记录节点是否被点击
      function pieClick(d) {
        var _this = this;
        if (pieClickFlag == false) {
          alert("checked");
          pieClickFlag = true;
        } else {
          alert("unckecked");
          pieClickFlag = false;
        }
      }

      // 版本标题的点击事件
      function versionNameClick(d) {
        let v = d3.select(this)._groups[0][0].textContent  // 获取当前点击的版本号
        let vTitle = [
      "V1.0.7",
      "V1.0.8",
      "V1.0.9",
      "V1.1.0",
      "V1.1.1",
      "V1.1.2",
      "V1.1.3",
      "V1.1.4",
      "V1.1.5",
      "V1.1.6",
      "V1.1.7",
      "V1.1.8",
      "V1.1.9",
      "V1.2.0",
      "V1.2.1",
      "V1.2.2",
      "V1.2.4",
      "V1.2.5",
      "V1.2.6",
      "V1.2.7",
      "V1.2.8",
      "V1.2.9",
      "V1.2.10",
      "V1.2.11",
      "V1.2.12",
      "V1.2.3",
      "Vgithub",
      "V1.2.13",
      "V1.2.14",
      "V1.2.15",
      "V1.2.16"
        ];
        let index = vTitle.indexOf(v)
        if(_this.$store.state.isComparison == false){ 
          _this.$store.state.issuesVersion = 'transitfeed-' + v.slice(1)   // 修改全局变量 非比较模式下更改当前选中版本
          _this.$store.state.singleVersion = index.toString() + '--transitfeed-' + v.slice(1)   // 修改全局变量 非比较模式下更改当前选中版本
        }
      }

            // 文件名的点击事件
      function filenameClick(){
        //第一次点击
        if(_this.filenameClickNum == 0){
          d3.select(d3.select(this)._groups[0][0].previousSibling).attr('d', "M-107,-4 L-104,-1 L-107,2")
          // d3.select(d3.select(this)._groups[0][0].previousSibling).attr('d', "M-109,-2 L-105,-2 L-107,2 L-109,-2")
          _this.filenameClickNum = 1
        }else{
          d3.select(d3.select(this)._groups[0][0].previousSibling).attr('d', "M-109,-2 L-105,-2 L-107,2")
          // d3.select(d3.select(this)._groups[0][0].previousSibling).attr('d', "M-109,-3 L-107,-1 L-109,1 L-109,-3")
          _this.filenameClickNum = 0
        }
      }

      function versionNameMouseOver(d) {
        var id = d3.select(this)._groups[0][0].id; // 获取选中的版本号
        var Gselection = d3.selectAll("#g_" + id)._groups[0];
        d3.selectAll(".pieNode")
          .filter(function(d, i) {
            // filter返回为false的时候会被过滤掉
            for (var i = 0; i < Gselection.length; i++) {
              if (d3.select(this)._groups[0][0] == Gselection[i]) return false;
              else continue;
            }
            return true;
          })
          .attr("opacity", "0.1");
      }

      function versionNameMouseOut(d) {
        d3.selectAll(".pieNode").attr("opacity", "1");
      }
    },
    drawLegend(){
      // 绘制渐变
      var legendSvg = d3.select('#legendDefine').append('svg').attr('class', 'legendSvg').attr('width', '140px').attr('height', '520px')


    ////////////////////////////////////////定义 表示commit提交次数的比例尺
    var commitG = legendSvg.append('g').attr('class', 'commirG').attr('transform', 'translate(20, 70)')
    var b = d3.rgb(50, 50, 50);	//红色
    var a = d3.rgb(230, 220, 210);	//绿色
    commitG.append('text').text("less")
                      .style('font-size', '12px')
                      .attr('text-anchor', 'middle')
    var defs = commitG.append("defs");

    var linearGradient = defs.append("linearGradient")
                .attr("id","linearColor")
                .attr("x1","0%")
                .attr("y1","0%")
                .attr("x2","100%")
                .attr("y2","0%");

    var stop1 = linearGradient.append("stop")
            .attr("offset","0%")
            .style("stop-color",a.toString());

    var stop2 = linearGradient.append("stop")
            .attr("offset","100%")
            .style("stop-color",b.toString());

                    //添加一个矩形，并应用线性渐变
    var commitLegend = commitG.append("rect")
            .attr("width", 100)
            .attr("height", 10)
            .style("fill","url(#" + linearGradient.attr("id") + ")");
            
    commitG.append('text').text("more")
                      .style('font-size', '12px')
                      .attr('x', '100')
                      .attr('y', '0')
                      .attr('text-anchor', 'middle')

    commitG.append('rect')
            .attr("x", 0)
            .attr("y", 36)
            .attr("width", 20)
            .attr("height", 6)
            .style("fill","#ffefae");
    commitG.append('text')
    .text('folder')
            .attr("x", 30)
            .attr("y", 43)
            .style('font-size', '12px')


    ////////////////////////////////////////定义表示代码质量的比例尺
    var metricG = legendSvg.append('g').attr('class', 'commirG').attr('transform', 'translate(60, 160)')
    // metricG.append('circle')
    // .attr('cx', '3')
    // .attr('cy', '0')
    // .attr('r', '6')
    // .attr('fill', '#a3caeb')
    // metricG
    // .append('text')
    // .text('code smell')
    // .attr('x', '19')
    // .attr('y', '3')
    // .style('font-size', '12px')

    
    // metricG.append('circle')
    // .attr('cx', '3')
    // .attr('cy', '22')
    // .attr('r', '6')
    // .attr('fill', '#ffc700')
    // metricG
    // .append('text')
    // .text('bug')
    // .attr('x', '19')
    // .attr('y', '25')
    // .style('font-size', '12px')

    
    // metricG.append('circle')
    // .attr('cx', '3')
    // .attr('cy', '44')
    // .attr('r', '6')
    // .attr('fill', '#ca64ea')
    // metricG
    // .append('text')
    // .text('vulnerability')
    // .attr('x', '19')
    // .attr('y', '47')
    // .style('font-size', '12px')

    // 绘制饼图
    let legendDataset =[5, 2, 1];
    let legendName =['code smell', 'bug', 'vulnerability'];
    let legendColor = ['#a3caeb', '#ffc700', '#ca64ea']
    // 新建一个饼图
    let legendPie = d3.pie();
    //新建一个弧形生成器
    let legendinnerRadius = 0;//内半径
    let legendouterRadius = 6;//外半径
    let legendarc_generator = d3.arc()
    		.innerRadius(legendinnerRadius)
    		.outerRadius(legendouterRadius);
    let legendpPieData = legendPie(legendDataset);
    let locationx = [35, -22, 5]
    let locationy = [2, 3, -12]
    let gs = metricG.selectAll(".arcG")
    		.data(legendpPieData)
    		.enter()
    		.append("g")
        .attr('class', 'arcG')
    //绘制饼状图的各个扇形
    gs.append("path")
    		.attr("d",function(d){
    			return legendarc_generator(d);//往弧形生成器中出入数据
    		})
    		.attr("fill",function(d,i){
    			return legendColor[i];//设置颜色
    		});
    //绘制饼状图上面的文字信息
    gs.append("text")
    		.attr("transform",function(d, i){//位置设在中心处
    			return "translate("+locationx[i] +', ' + locationy[i]+")";
    		})
    		.attr("text-anchor","middle")
    		.attr("class","legendName")
    		.style("font-size","10px")
    		.text(function(d, i){
    			return legendName[i];
    		})
    },


    changeShowCommitAndPie(){
      d3.selectAll(".commitRect").attr("opacity", 0);
      d3.selectAll(".smallPie").attr("opacity", 0);
      for(let i= 0; i<this.$store.state.showCommitAndPie.length; i++){
        if('show commit' == this.$store.state.showCommitAndPie[i]){    // 显示commit
          d3.selectAll(".commitRect").attr("opacity", 1);
        }
        if('show pie' == this.$store.state.showCommitAndPie[i]){    // 显示pie
          d3.selectAll(".smallPie").attr("opacity", 1);
        }
      }
    }
  }
};
</script>


<style scoped>
    .node rect {     /* 矩形外框*/
    cursor: pointer;
    fill-opacity: 0.5;
    stroke-width: 0.5px;
  }

  /* .node text { // 矩形的文本 */
    /* font: 7px sans-serif; */
    /* pointer-events: none; */
    /* dominant-baseline: central; // 设置文本垂直排列 */
    /* text-anchor:inherit; */
  /* } */

  #main-view{
    position: relative;
    float:left;
    overflow-y: scroll;
    overflow-x: auto;
    /* overflow-x: hidden; */
    height: 500px; /*垂直 500 < 550*/
    width: 1000px; /*水平 150 < 200*/
  }
  
  .versionName{
    text-anchor:middle;   /* 对齐（开始，中间或结束对齐）相对于给定点的文本字符串 */
    font-size: 10px;
    font-weight: bold;
    color: #b5b5b5;
    font-family: Arial, Helvetica, sans-serif;
  }
  
  .link {    /* 节点的连接*/ 
    fill: none;
    stroke: #73bfd4;
    stroke-width: 1.5px;
  }


  .tooltip{    /* 这个设置没有用处 */
    position: absolute;
    width:auto;
    height:auto;
    background:#84b6d1;
    /* border :1px solid #ccc; */
    border-radius: 5px;
  }


</style>