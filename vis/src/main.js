/*
 * @Descripttion: 
 * @version: 
 * @Author: Yolanda
 * @Date: 2021-03-08 19:46:17
 * @LastEditors: Yolanda
 * @LastEditTime: 2021-04-20 10:11:50
 */
// The Vue build version to load with the `import` command
// (runtime-only or standalone) has been set in webpack.base.conf with an alias.
import Vue from 'vue'
import App from './App'
import router from './router'
import * as d3 from "d3"
Vue.prototype.$d3 = d3


// 引入element
import ElementUI from 'element-ui';
import 'element-ui/lib/theme-chalk/index.css';
Vue.use(ElementUI);

Vue.config.productionTip = false

/*import axios*/
import axios from 'axios'
Vue.prototype.$axios=axios
axios.defaults.baseURL = '/api'
axios.defaults.timeout = 15000;  //超时响应
axios.defaults.headers.post['Content-Type'] = 'application/x-www-form-urlencoded;charset=UTF-8'; // 配置请求头（推荐）
axios.defaults.withCredentials = true;   // axios 默认不发送cookie，需要全局设置true发送cookie
Vue.config.productionTip = false


// import vuex
import { store } from './store/store';
import $ from 'jquery'
// import vue-codemirror
import VueCodeMirror from 'vue-codemirror'
import 'codemirror/lib/codemirror.css'
Vue.use(VueCodeMirror)

// import echarts
import echarts from 'echarts'
Vue.prototype.$echarts = echarts

// 控制页面布局的缩放
import util from "./assets/js/util.js";
util.zoom();
window.onresize = () => {
  util.zoom();
};
/* eslint-disable no-new */
new Vue({
  el: '#app',
  router,
  store: store,
  components: { App },
  template: '<App/>'
})
