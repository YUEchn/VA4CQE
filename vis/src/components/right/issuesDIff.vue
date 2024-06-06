<template>
<div id = "table">
  <el-table
    ref="filterTable"
    :data="tableData"
    style="width: 100%">
    <el-table-column
      prop="tag"
      label="Type"
      width="80"
      :filters="[{ text: 'code smell', value: 'code smell' }, { text: 'bug', value: 'bug' }, { text: 'vulnerabilty', value: 'vulnerabilty' }]"
      :filter-method="filterTag"
      filter-placement="bottom-end">
      <template slot-scope="scope">
        <el-tag
          :type="scope.row.tag === 'code smell' ? 'warning' : scope.row.tag === 'vulnerability' ? 'danger' : 'primary'"
          disable-transitions>{{scope.row.tag}}</el-tag>
      </template>
    </el-table-column>
    <el-table-column
      prop="filename"
      label="Filename"
      width="110">
    </el-table-column>
    <el-table-column
      prop="descirption"
      label="Message"
      width="240">
    </el-table-column>
    <el-table-column
      prop="line"
      label="Line"
      width="50">
    </el-table-column>
    <el-table-column
      prop="severityAdd"
      label="Severity"
      width="70">
    </el-table-column>
  </el-table>
  </div>
</template>

<script>
  export default {
    data() {
      return {
        addV1: '',
        addV2: '',
        tableData: []
      }
    },
    methods: {
      filterTag(value, row) {
        return row.tag === value;
      },
      filterHandler(value, row, column) {
        const property = column['property'];
        return row[property] === value;
      },
      initIssuesAdd(){
        this.addV1 = this.$store.state.twoVersion1
        this.addV2 = this.$store.state.twoVersion2
        this.$axios({
          method:'post',
          url:'/issuesAddDt',
          data:{
            v1: this.addV1,
            v2: this.addV2
          }
        }).then(res=>{
          this.tableData = res.data
        })
      }
    }
  }
</script>
<style>
#table{
  width: 550px;
  height: 900px;
  overflow: scroll;
}
.el-table-filter {
  position: absolute !important;
  top: 127px !important;
  left: 1483px !important;
}
.el-table__body-wrapper {
  overflow: auto;
} 

.el-table__body-wrapper {
  height: 90%;
}

#table.cell{
  line-height: 13px;
  padding-right: 0;
  padding-left: 0;
  line-height: 12px;
}

.el-table td, .el-table th{
  font-size: 10px;
  padding: 0
}

.el-table th, .el-table tr{
  font-size: 12px;
}
.el-checkbox__label{
  font-size: 10px;
}
.el-table-filter__bottom button{
  font-size: 10px;
}

.el-tag{
  font-size: 10px;
  display: inline;
  line-height: 0;
  padding:0
}
</style>
