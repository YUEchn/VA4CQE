<template>
  <div>
    <label>{{ filename }} </label>
    <codemirror
      v-model="code"
      :options="cmOption"
      @cursorActivity="cursorActivityFunc"
      @update="updateFunc"
    />
    <div class="issuesTable">
      <el-table ref="filterTable" :data="tableData" style="width: 100%">
        <el-table-column
          width="280"
          prop="message"
          label="message"
        ></el-table-column>
        <el-table-column prop="severity" label="severity" width="80"></el-table-column>
        <el-table-column prop="filetags" label="filetags" width="100">
        </el-table-column>
        <el-table-column
          prop="types"
          label="types"
          width="70">
          <template slot-scope="scope">
            <el-tag
              :type="scope.row.types === 'code smell' ? 'primary' : scope.row.types === 'vulnerability' ? 'danger' : 'warning'"
              disable-transitions
              >{{ scope.row.types }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script>
import dedent from "dedent";
import { codemirror } from "vue-codemirror";

// language
import "codemirror/mode/python/python.js";

// theme css
import "codemirror/theme/base16-light.css";

// require active-line.js
import "codemirror/addon/selection/active-line.js";

// closebrackets
import "codemirror/addon/edit/closebrackets.js";

// keyMap
import "codemirror/mode/clike/clike.js";
import "codemirror/addon/edit/matchbrackets.js";
import "codemirror/addon/comment/comment.js";
import "codemirror/addon/dialog/dialog.js";
import "codemirror/addon/dialog/dialog.css";
import "codemirror/addon/search/searchcursor.js";
import "codemirror/addon/search/search.js";
import "codemirror/keymap/emacs.js";
import * as d3 from "d3";

export default {
  name: "codemirror-example-python",
  components: {
    codemirror
  },
  data() {
    return {
      filename: "feedvalidator.py",
      fileDir: "",
      issuesVersion: "",
      currLine: "", // 当前光标所在的行
      cmOption: {
        autoCloseBrackets: true,
        tabSize: 4, // tab字符的宽度
        indentUnit: 4, //缩进单位
        smartIndent: true, // 自动缩进
        styleActiveLine: true,
        lineWrapping: false, //代码折叠 是否应滚动或换行以排长行;false(滚动)
        lineWiseCopyCut: true,
        lineNumbers: true, // 是否在左侧显示行号
        line: true,
        mode: "text/x-python", //编辑器模式支持的文件:text/javascript text/html  application/xml
        theme: "base16-light",
        foldGutter: true,
        autoRefresh: true, // 自动触发刷新
        gutters: ["CodeMirror-lint-markers", "CodeMirror-foldgutter"],
        indent: true,
        // keyMap: "emacs",
        readOnly: true //设置编辑器为只读
      },
      code: "",
      issues: "",
      // 表格的数据
      tableData: []
    };
  },
  computed: {
    isChangefilenameDir() {
      return this.$store.state.filenameDir; // 监听全局变量，选择的文件
    },
    isChangeIssuesVersion() {
      return this.$store.state.issuesVersion; // 监听全局变量，选择的文件
    }
  },
  watch: {
    isChangefilenameDir(old, newVlaue) {
      // 改变了文件
      this.initFileIssues();
    },
    isChangeIssuesVersion(old, newVlaue) {
      // 改变了版本号
      this.initFileIssues();
    }
  },
  mounted(){
    this.setHeight()
  },
  methods: {
    // 光标移动时获取所在的行
    cursorActivityFunc() {
      document.getElementsByClassName("CodeMirror-activeline");
      var _this = this;
      this.$nextTick(() => {
        try {
          _this.currLine = document.getElementsByClassName("CodeMirror-activeline")[0].children[2].innerText;  //获取当前内容的行
           _this.tableData = []    // 先清原始数据
          let lineIssues = _this.issues[_this.currLine]  // 获取当前行存在的问题
          for(let i=0;i<lineIssues['CODE_SMELL'].length; i++){
            _this.tableData.push({severity: lineIssues['CODE_SMELL'][i][0],message:lineIssues['CODE_SMELL'][i][1], types:'code smell', filetags: lineIssues['CODE_SMELL'][i][2]})
          }          
          for(let i=0;i<lineIssues['BUG'].length; i++){
            _this.tableData.push({severity: lineIssues['BUG'][i][0],message:lineIssues['BUG'][i][1], types:'bug', filetags: lineIssues['BUG'][i][2]})
          }          
          for(let i=0;i<lineIssues['VULNERABILITY'].length; i++){
            _this.tableData.push({severity: lineIssues['VULNERABILITY'][i][0],message:lineIssues['VULNERABILITY'][i][1], types:'vulnerability', filetags: lineIssues['VULNERABILITY'][i][2]})
          }
        } catch (err) {
          console.log(err);
        }
      });
    },
    // 从后端获取数据
    initFileIssues() {
      this.fileDir = this.$store.state.filenameDir;
      this.issuesVersion = this.$store.state.issuesVersion;
      console.log(this.issuesVersion, this.fileDir)
      this.$axios({
        method: "post",
        url: "/issuesDt",
        data: {
          fileDir: this.fileDir, // 文件路径和文件名
          version: this.issuesVersion // 文件的版本号
        }
      }).then(res => {
        this.issues = res.data[1];
        this.code = res.data[0];
        this.filename = this.fileDir.split("/")[
          this.fileDir.split("/").length - 1
        ];
      });
    },
    // codemirror的更新函数
    updateFunc() {
      var codeLines = d3.selectAll(".CodeMirror-code .CodeMirror-linenumber")
        ._groups[0];
      var startLine = d3.select(codeLines[0])._groups[0][0].innerText - 1;
      
      console.log('更新了: ',d3.select(codeLines[0])._groups[0][0].innerText - 1);
      try {
        for (let i = 0; i < codeLines.length; i++) {
          // 循环每一行
          var aixs = 26;
          // 如果没有svg，则创建svg，在更新之后svg还存在但是里面的元素会变化
          if (d3.select(d3.select(codeLines[i])._groups[0][0].parentNode).select("svg").empty()) {
            d3.select(d3.select(codeLines[i])._groups[0][0].parentNode)
              .append("svg")
              .attr("id", "msvg" + (i + startLine).toString());
          }
            if (this.issues[i + startLine].CODE_SMELL.length != 0) {
              d3.select("#msvg" + (i + startLine - 1).toString())
                .append("rect")
                .attr("class", "CODE_SMELL")
                .attr("x", aixs)
                .attr("y", 5)
                .attr("width", 5)
                .attr("height", 5)
                .attr("fill", "#007acc")
              aixs += 5;
            }
            if (this.issues[i + startLine].BUG.length != 0) {
              d3.select("#msvg" + (i + startLine - 1).toString())
                .append("rect")
                .attr("class", "BUG")
                .attr("x", aixs)
                .attr("y", 5)
                .attr("width", 5)
                .attr("height", 5)
                .attr("fill", "#ffefae");
              aixs += 5;
            }
            if (this.issues[i + startLine].VULNERABILITY.length != 0) {
              d3.select("#msvg" + (i + startLine - 1).toString())
                .append("rect")
                .attr("class", "VULNERABILITY")
                .attr("x", aixs)
                .attr("y", 5)
                .attr("width", 5)
                .attr("height", 5)
                .attr("fill", "#ca64ea");
              aixs += 5;
            }
        }
      } catch (err) {}
    },
    // 表格的一系列方法 被删除了
    // 动态设置显示区域的宽度
    setHeight(){
      if(this.$store.state.isComparison == false){
        document.getElementsByClassName("CodeMirror")[0].style.height = 727+'px';
      }else{
        document.getElementsByClassName("CodeMirror")[0].style.height = 420+'px';
      }
    }
  }
};
</script>

<style>
label{
  font-size:14px;
  font:bold
}
.CodeMirror-scroll {
  padding-bottom: 0 !important;
  margin-right: 0;
  margin-bottom: 0;
  overflow-x: hidden !important;
}
/* 设置代码行与行号之间的距离 */
.CodeMirror-line {
  padding-left: 20px !important;
}
.CodeMirror-linenumber .CodeMirror-gutter-elt{
  margin-right: 10px;
}

.el-table-column {
  height: 20px;
}
.el-table {
  font-size: 12px;
}
.el-button {
  margin-top: 2px;
  padding: 0;
  font-size: 12px;
}
.issuesTable {
  /* margin-left: 10px; */
  height: 101px;
}
tr.el-table td,
.el-table th {
  padding: 0;
}
.el-table td,
.el-table th {
  padding: 0;
}
.el-tag {
  display: inline;
}

.el-table__body-wrapper {
  overflow: auto;
}

.el-table__body-wrapper {
  height: 70%  !important
}
</style>
