/*
 * @Descripttion: 
 * @version: 
 * @Author: Yolanda
 * @Date: 2021-04-15 13:45:09
 * @LastEditors: Yolanda
 * @LastEditTime: 2021-04-15 14:48:31
 */
import constant from "./constant";
export default {
    zoom() {
        let x = window.innerWidth / constant.constant.PAGE_WIDTH;
        let y = window.innerHeight / constant.constant.PAGE_HEIGHT;
        let oBody = document.getElementsByTagName('body')[0];
        oBody.style.transform = `scale(${x}, ${y})`;
        oBody.style.webkitTransform = `scale(${x}, ${y})`;/* for Chrome || Safari */
        oBody.style.msTransform = `scale(${x}, ${y})`;/* for Firefox */
        oBody.style.mozTransform = `scale(${x}, ${y})`;/* for IE */
        oBody.style.oTransform = `scale(${x}, ${y})`;/* for Opera */     
    }
};
