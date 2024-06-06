import Vue from 'vue';
import Vuex from 'vuex';  
Vue.use(Vuex)   //显式使用Vuex插件，一般写在src/main.js中，或者写在其它js中然后再在main.js中引入

export const store = new Vuex.Store({
    state: {
        singleVersion: '0--transitfeed-1.0.7',     // 非比较模式下的默认版本
        twoVersion1: '0--transitfeed-1.0.7',       // 比较模式下的第一个版本
        twoVersion2: '1--transitfeed-1.0.8',        // 比较模式下的第二个版本
        filenameDir: 'feedvalidator.py',    // 当前选中的文件，用路径来唯一标识
        issuesVersion: 'transitfeed-1.0.7',    // 当前选中的版本, 加入这个变量是为了区分是否有两个雷达树图
        isComparison: false,   // 表示是否在比较模式下，默认为非比较模式下 
        showCommitAndPie: ['show commit','show pie'],     // 默认显示commit数据和饼图数据
    }
})