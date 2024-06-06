<!--
 * @Descripttion: 
 * @version: 
 * @Author: Yolanda
 * @Date: 2021-03-08 19:46:17
 * @LastEditors: Yolanda
 * @LastEditTime: 2021-04-20 10:11:58
-->
<template>
  <div id="app">
    <div id="titleBox">
      <p id="title">Visual Analystics System for Code Quality Evolution</p>
    </div>
    <!-- 视图部分 -->
    <div id="content">
      <!-- 左侧视图 -->
      <div id="leftView">
        <div id="controlPanel">
          <div style="margin-left: 20px">
            <el-switch
              style="display: block"
              v-model="switchValue"
              active-color="#13ce66"
              inactive-color="#dcdfe6"
              active-text="Comparison"
              inactive-text="Not comparison"
              @change="changeSwitch()"
            ></el-switch>
            <div>
              <p><strong>version-1</strong></p>
              <el-select
                v-model="selectVersion1"
                placeholder="# 1"
                style="height:30px; width:217px; line-height: 30px"
                @change="changeVersion1()"
                @click.native="foucestp1"
              >
                <el-option
                  v-for="item in versionSelectOptions"
                  :key="item.label"
                  :value="item.value"
                >
                </el-option>
              </el-select>
            </div>
            <div>
              <p><strong>version-2</strong></p>
              <el-select
                v-model="selectVersion2"
                placeholder="# 2"
                style="height:30px; width:217px;line-height: 30px"
                :disabled="IsDisabled"
                @click.native="foucestp2"
              >
                <el-option
                  v-for="item in versionSelectOptions"
                  :key="item.label"
                  :value="item.value"
                >
                </el-option>
              </el-select>
            </div>
            <br />
            <el-button
              type="primary"
              plain
              style="height:30px; width:217px; font-size: 14px; line-height: 0"
              @click="getComparison(selectVersion1, selectVersion2)"
              >COMPARE</el-button
            >
          <el-checkbox-group v-model="checkList" class = 'changeMainView' @change="changeCheck()">
              <el-checkbox label="show commit"></el-checkbox>
              <el-checkbox label="show pie"></el-checkbox>
            </el-checkbox-group>
          </div>
        </div>
        <div id = 'statistics'>
          <statistics />
        </div>
        <div id="leftBottom">
          <tagView ref="tagViewRef" />
        </div>
      </div>
      <!-- 中心视图 -->
      <div id="centerView">
        <div id="topView">
          <mainView />          <!-- 中心位视图 -->
        </div>
        <div id="bottomView">
          <h6 style="margin-block-start: 0; margin-block-end: 0;">FILE ISSUES VIEW</h6>
          <div class="singleVersion" v-if="area == 'singleVersion'">
            <radarTreeView ref="singleRadarTree"/>           <!-- 单个雷达树视图 -->

          </div>
          <div class="twoVersion" v-if="area == 'twoVersion'" style="display: flex">
            <div class = "twoRadarTreeViewDiv">
              <twoRadarTreeView ref="twoRadarTree" />  <!--两个雷达树视图 -->
            </div>
          </div>
        </div>
      </div>
      <!-- 右侧视图 -->
      <div id="rightView">
        <div class="codePanel">
          <div class="singleVersion" v-if="area == 'singleVersion'">  <!-- 单个版本情况下的当前选中文件的issues-->
              <fileIssues ref="issuesFile"  />   <!--代码issues视图 -->
          </div>
          <div class="twoVersion" v-if="area == 'twoVersion'">
            <el-tabs v-model="activeName" @tab-click="handleClick">
              <el-tab-pane label="code" name="first">
                <div style = 'height:521px'>
                  <fileIssues ref="issuesFile" />    <!-- 两个版本情况下的当前选中文件的issues -->
                </div>
                 <diffView ref="diff" />     <!--代码差异视图 -->
              </el-tab-pane>
              <el-tab-pane label="issuesAdd" name="second">
                <div class = "issuesDiffTableDiv">
                  <issuesdiffTable ref="issuesAdd" />
                </div>
              </el-tab-pane>
          </el-tabs>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import mainView from "./components/center/mainView";
import radarTreeView from "./components/center/radarTreeView";
import diffView from "./components/right/diffView";
import twoRadarTreeView from "./components/center/twoRadarTreeView";
import fileIssues from "./components/right/fileIssues";
import tagView from './components/left/parallel';
import statistics from './components/left/statistics';
import issuesdiffTable from './components/right/issuesDIff'

import * as d3 from "d3";
import $ from 'jquery'
export default {
  name: "App",
  data() {
    return {
      switchValue: false, // 开关按钮绑定的数据, 值为true或者false
      versionSelectOptions: [],
      selectVersion1: "transitfeed-1.0.7", // 版本选择绑定的值,option中选择的值
      selectVersion2: "transitfeed-1.0.8", // 版本选择绑定的值
      area: "singleVersion", // 默认单个版本下的视图
      IsDisabled: true,
      versionDict: {},
      _this: "",
      activeName: 'first',
      checkList: ['show commit','show pie']
    };
  },
  components: {
    mainView,
    radarTreeView,
    diffView,
    twoRadarTreeView,
    fileIssues,
    tagView,
    statistics,
    issuesdiffTable
  },

  computed:{   // 监听全局变量的时候使用这种方法
    isChangeSingleVersionApp(){
      return this.$store.state.singleVersion
    }
  },

  watch:{
    isChangeSingleVersionApp: function(){   // 监听在非比较模式下选中的版本，用来更新下拉框的值
      this.selectVersion1 = this.$store.state.singleVersion.split('--')[1]
    }
  },

  mounted() {
    var versionName = [
      "1.0.7",
      "1.0.8",
      "1.0.9",
      "1.1.0",
      "1.1.1",
      "1.1.2",
      "1.1.3",
      "1.1.4",
      "1.1.5",
      "1.1.6",
      "1.1.7",
      "1.1.8",
      "1.1.9",
      "1.2.0",
      "1.2.1",
      "1.2.2",
      "1.2.4",
      "1.2.5",
      "1.2.6",
      "1.2.7",
      "1.2.8",
      "1.2.9",
      "1.2.10",
      "1.2.11",
      "1.2.12",
      "github",
      "1.2.3",
      "1.2.13",
      "1.2.14",
      "1.2.15",
      "1.2.16"
    ];
    ////////////////////// 初始化下拉列表的数据 ////////////////////////////
    for (let i = 0; i < versionName.length; i++) {
      this.versionSelectOptions.push({
        label: i + "--transitfeed-" + versionName[i],
        value: "transitfeed-" + versionName[i]
      });
      this.versionDict["transitfeed-" + versionName[i]] = i.toString();
    }
    this.showSingleRadarTree();
    this.showIssuesFile();
    this.showTag()
  },
  methods: {
    // 点击第一个下拉列表
    foucestp1(){
        let dpLength = document.getElementsByClassName("el-select-dropdown").length
        for(let i=0;i<dpLength; i++){
          document.getElementsByClassName("el-select-dropdown")[i].classList.add("dp1");
        }
    },
    // 点击第二个下拉列表
    foucestp2(){
        let dpLength = document.getElementsByClassName("el-select-dropdown").length
        for(let i=0;i<dpLength; i++){
          document.getElementsByClassName("el-select-dropdown")[i].classList.add("dp2");
        }
    },

    // 切换比较模式和非比较模式
    changeSwitch() {
      let vm = this;
      this.switchValue != this.switchValue;
      if (this.switchValue == false) {
        // 设置为单个版本的情况下
        this.IsDisabled = true;
        this.area = "singleVersion";
        this.$store.state.singleVersion = this.versionDict[this.selectVersion1] + "--" + this.selectVersion1;
        this.$store.state.issuesVersion = this.selectVersion1;
        this.$store.state.isComparison = false   // 修改全局状态为 非比较模式
        this.$nextTick(function() {
          this.showSingleRadarTree();    // 显示单个雷达树图
          this.showTag()                 // 显示tag标签
          this.showIssuesFile()        // 显示当个文件的详细问题
        });  
      } else {
        this.IsDisabled = false; // 设置第二个下拉列表可用
        this.area = "twoVersion"; // 双版本的视图
        this.$store.state.isComparison = true   // 修改全局状态为 比较模式
        this.$store.state.twoVersion1 = this.versionDict[this.selectVersion1] + "--" + this.selectVersion1;
        this.$store.state.twoVersion2 = this.versionDict[this.selectVersion2] + "--" + this.selectVersion2;
        this.$nextTick(function() {
          this.showTwoRadarTree()      // 显示两个雷达树图
          this.showDiff()              // 显示两个版本的差异
          this.showIssuesFile()        // 显示当个文件的详细问题
          this.showTag()               // 显示tag标签
          this.showIssuesAdd()         // 增加的问题
        });
      }
    },

    // 在非比较模式下改变第一个单选框的值
    changeVersion1() {
      if (this.switchValue == false) {
        this.$store.state.singleVersion = this.versionDict[this.selectVersion1] + "--" + this.selectVersion1;
        this.$store.state.issuesVersion = this.selectVersion1;   // 监听，更改则执行当个文件的详细
        this.showSingleRadarTree();
        this.showTag()               // 显示tag标签
      }
    },
    // 在比较模式下通过提交按钮更新右侧的面板的内容 v1 v2没有序列值
    getComparison(v1, v2) {
      if (this.switchValue == true) {
        this.$store.state.twoVersion1 = this.versionDict[v1] + "--" + v1;
        this.$store.state.twoVersion2 = this.versionDict[v2] + "--" + v2;
        this.showTwoRadarTree()      // 显示两个雷达树图
        this.showIssuesAdd()  // 相邻版本之间增加的issues
        // this.showTag()               // 显示tag标签
        // this.showDiff()               // 显示tag标签
      }
    },

    showSingleRadarTree() {
      try {
        this.$refs.singleRadarTree.initRadarTree(); // 父组件调用子组件中的方法，通过ref
      } catch (e) {
        console.log(e);
      }
    },
    // 显示两个雷达树图
    showTwoRadarTree() {
      try {
        this.$refs.twoRadarTree.initTwoRadarTree(); // 父组件调用子组件中的方法，通过ref
      } catch (e) {
        console.log(e);
      }
    },

    // 显示差异视图
    showDiff() {
      try {
        this.$refs.diff.initDiffView(); // 父组件调用子组件中的方法，通过ref
      } catch (e) {
        console.log(e);
      }
    },
  
    // 显示单个文件的issues视图
    showIssuesFile() {
      try {
        this.$refs.issuesFile.initFileIssues(); // 父组件调用子组件中的方法，通过ref
      } catch (e) {
        console.log(e);
      }
    },

    // 显示tag数据的视图  
    showTag(){ 
      try {
        this.$refs.tagViewRef.initTagView(); // 父组件调用子组件中的方法，通过ref
      } catch (e) {
        console.log(e);
      }
    },

    // 显示两个相邻版本之间增加的issues  issuesAdd
    showIssuesAdd(){ 
      try {
        this.$refs.issuesAdd.initIssuesAdd(); // 父组件调用子组件中的方法，通过ref
      } catch (e) {
        console.log(e);
      }
    },

    handleClick(tab, event) {
        console.log(tab, event);
    },
    // 监听复选框
    changeCheck(){
      this.$store.state.showCommitAndPie = []
      for(let i= 0; i<this.checkList.length; i++){
        this.$store.state.showCommitAndPie.push(this.checkList[i])
      }
      for(let i= 0; i<this.checkList.length; i++){
        if('show commit' == this.$store.state.showCommitAndPie[i]){
          console.log('show commit')
        }
      }
    }
  }
};
</script>

<style>
html,
body {
  margin: 0;
  padding: 0;
  width: 2048px;
  height: 1038px;
  min-width: 960px;
  transform-origin: 0 0 0; /*指定缩放的基本点*/
  -moz-transform-origin: 0 0 0;
  -ms-transform-origin: 0 0 0;
  -webkit-transform-origin: 0 0 0;
  -o-transform-origin: 0 0 0;
  overflow: hidden;
}
p {
  font-family: "Times New Roman", Times, serif;
}
#app {
  font-family: "Avenir", Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#titleBox {
  height: 50px;
  width: 100%;
  /* width: 2048px; */
  background-color: #343a40;
}

#title {
  color: #2c3e50;
  color: black;
  color: white;
    font-size: 30px;
    margin-top: 7px;
    margin-left: 770px;
    /* float: center; */
    text-align: center;
    display: inline;
    position: absolute;
}

#content {
  width: 2048px;
  height: 975px;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  padding-top: 0;
}

#rightView {
  width: 550px;
  height: 980px;
  margin-right: 0;
  margin-left: 1.5px;
  border: 1px solid #e3e3e3;
}

#centerView {
  width: 1098px;
  height: 975px;
}
#topView {
  width: 1093px;
  height: 540px;
  border: 1px solid #e3e3e3;
  margin-left: 3px;
}

#bottomView {
  width: 1093px;
  height: 441px;
  border: 1px solid #e3e3e3;
  margin-left: 3px;
  margin-top: 2px;
}

#leftView {
  width: 400px;
  height: 980px;
  margin-left: 0;
  /* border:4px solid #e3e3e3; */
  border: 0;
}

#controlPanel {
  width: 400px;
  height: 270px;
  margin-left: 0;
  border: 1px solid #e3e3e3;
}

#leftBottom {
  width: 400px;
  height: 402px;
  margin-left: 0;
  border: 1px solid #e3e3e3;
}

#statistics{
  width: 400px;
  height: 310px;
  margin-left: 0;
  border: 1px solid #e3e3e3;

}

.twoRadarTreeViewDiv{
  width: 1093px;
  height: 441px;
  /* margin-left: 47px; */
}

.issuesDiffTableDiv{
  width: 550px;
  height: 900px;
  border-left: 1px solid #e3e3e3;
}


/*滚动条样式*/
::-webkit-scrollbar {
  /*滚动条整体样式*/
  width : 10px;  /*高宽分别对应横竖滚动条的尺寸*/
  height: 4px;
  }
  ::-webkit-scrollbar-thumb {
  /*滚动条里面小方块*/
  border-radius   : 10px;
  background-color: #c1c1c1;
  background-image: -webkit-linear-gradient(
      45deg,
      rgba(255, 255, 255, 0.2) 25%,
      transparent 25%,
      transparent 50%,
      rgba(255, 255, 255, 0.2) 50%,
      rgba(255, 255, 255, 0.2) 75%,
      transparent 75%,
      transparent
  );
  }
  ::-webkit-scrollbar-track {
  /*滚动条里面轨道*/
  background   : #f1f1f1;
  border-radius: 10px;
  }

  /* 设置卡片的位置 */
  .el-tabs__nav-scroll{
    padding-left:375px
  }

.changeMainView{
  margin-top: 10px;
}

.dp1{
  top:147px !important;
}

.dp2{
  top:234px !important;
}

.el-input__inner{
  height:40px !important
}
</style>
