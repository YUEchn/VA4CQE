/*
 * @Descripttion: 
 * @version: 
 * @Author: Yolanda
 * @Date: 2021-03-08 20:06:21
 * @LastEditors: Yolanda
 * @LastEditTime: 2021-04-20 22:37:01
 */
const express = require('express');
const bodyParser = require('body-parser');
const app = express();
const path = require('path');
const fs = require('fs');
const Diff2html = require('diff2html');
var callfile = require('child_process');   // 用于执行脚本的工具
app.use(bodyParser.json());



/*****************************API*****************************/
port = 3000
app.listen(port, function () {
    console.log("http://127.0.0.1:3000/data");
});


//设置允许跨域请求
app.all('*', function (req, res, next) {
    res.header('Access-Control-Allow-Origin', '*'); //访问控制允许来源：所有
    res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept'); //访问控制允许报头 X-Requested-With: xhr请求
    res.header('Access-Control-Allow-Metheds', 'PUT, POST, GET, DELETE, OPTIONS'); //访问控制允许方法
    res.header('X-Powered-By', 'nodejs'); //自定义头信息，表示服务端用nodejs
    res.header('Content-Type', 'application/json;charset=utf-8');
    res.setHeader('Cache-Control', 'public, max-age=120');      // 设置强缓存 时间间隔2min
    next();
});


// 设置路由
app.get("/", (req, res) => {
    res.send("hello world!")
})

// 主视图需要的数据
app.get("/mainDt", function (req, res) {
    let file = path.join(__dirname, 'data/PYfileWithTCMstatics.json')
    fs.readFile(file, 'utf-8', function (err, data) {
        if (err) {
            console.log(err)
        } else {
            res.send(data);
            res.end();
        }
    })
})

// 单个雷达树图  通过前端传参获取数据
app.post("/radarTreeDt", function (req, res) {
    let version = req.body.versionNumber
    let file = path.join(__dirname, 'data/everyVersion/' + version + '.json')
    fs.readFile(file, 'utf-8', function (err, data) {
        if (err) {
            console.log(err)
        } else {
            res.send(data);
            res.end();
        }
    })

})


//  两个雷达树图  遍历json对象数据，获取最大值
function getMaxMetric(data) {
    if (depth == 0) {
        bugMax = Math.max(bugMax, data['metrics']['bugs'])
        code_smellMax = Math.max(code_smellMax, data['metrics']['code_smells'])
        vulnerabilityMax = Math.max(vulnerabilityMax, data['metrics']['vulnerabilities'])
        ccMax = Math.max(ccMax, data['metrics']['cognitive_complexity'])
        dlMax = Math.max(dlMax, data['metrics']['duplicated_lines_density'])
        clMax = Math.max(clMax, data['metrics']['comment_lines_density'])
        depth = 1
        getMaxMetric(data['children'])
    }
    else {
        for (let index = 0; index < data.length; index++) {
            bugMax = Math.max(bugMax, isNaN(data[index]['metrics']['bugs']) ? bugMax : data[index]['metrics']['bugs'])
            code_smellMax = Math.max(code_smellMax, isNaN(data[index]['metrics']['code_smells']) ? code_smellMax : data[index]['metrics']['code_smells'])
            vulnerabilityMax = Math.max(vulnerabilityMax, isNaN(data[index]['metrics']['vulnerabilities']) ? vulnerabilityMax : data[index]['metrics']['vulnerabilities'])
            ccMax = Math.max(ccMax, isNaN(data[index]['metrics']['cognitive_complexity']) ? ccMax : data[index]['metrics']['cognitive_complexity'])
            dlMax = Math.max(dlMax, isNaN(data[index]['metrics']['duplicated_lines_density']) ? dlMax : data[index]['metrics']['duplicated_lines_density'])
            clMax = Math.max(clMax, isNaN(data[index]['metrics']['comment_lines_density']) ? clMax : data[index]['metrics']['comment_lines_density'])
            if (data[index]['value'] == "dir") {
                getMaxMetric(data[index]['children'])
            }
        }
    }
    return
}
//  两个雷达树图   通过前端传参获取数据
var bugMax = 0, code_smellMax = 0, vulnerabilityMax = 0, ccMax = 0, dlMax = 0, clMax = 0, depth;
app.post("/twoRadarTreeDt", function (req, res) {
    let v1 = req.body.versionNumber1
    let v2 = req.body.versionNumber2
    let file1 = path.join(__dirname, 'data/everyVersion/' + v1 + '.json')
    let file2 = path.join(__dirname, 'data/everyVersion/' + v2 + '.json')

    fs.readFile(file1, 'utf-8', function (err, data1) {
        if (err) {
            console.log(err)
        } else {
            let ress = []
            ress[0] = JSON.parse(data1)
            depth = 0
            getMaxMetric(JSON.parse(data1))
            fs.readFile(file2, 'utf-8', function (err, data2) {
                if (err) {
                    console.log(err)
                } else {
                    ress[1] = JSON.parse(data2)
                    depth = 0
                    getMaxMetric(JSON.parse(data2))
                    ress[2] = { 'bugMax': bugMax, 'code_smellMax': code_smellMax, 'vulnerabilityMax': vulnerabilityMax, 'ccMax': ccMax, 'dlMax': dlMax, 'clMax': clMax }
                    res.send(ress)
                    res.end()
                }
            })
        }
    })
})


// 处理差异视图 || 执行一个文件，但是需要执行sh命令，第二个参数是git bash所在的位置
app.post("/diffDt", function (req, res) {
    let v1, v2;
    if (req.body.version1 == '25--transitfeed-github') {
        v1 = 'transitfeed-github'
        v2 = req.body.version2.split('transitfeed-')[1]
    }
    else if (req.body.version2 == '25--transitfeed-github') {
        v1 = req.body.version1.split('transitfeed-')[1]
        v2 = 'transitfeed-github'
    }
    else {
        v1 = req.body.version1.split('transitfeed-')[1]
        v2 = req.body.version2.split('transitfeed-')[1]
    }
    // 将数据写进文件中 
    console.log('处理差异视图',v1, v2)
    // 先清空目标文件
    fs.writeFile('data/diff/diff.txt', '', function (error) {
        if (error) {
            console.log('写入失败')
        } else {
            console.log('写入成功了')
        }
    })
    let str = 'cd D:/Project/diplomaProject/data/raw/transitfeed/clone/transitfeed-1.2.16\ngit --no-pager diff ' + v1 + ' ' + v2 + ' >> D:/Project/diplomaProject/back/data/diff/diff.txt'
    fs.writeFile('data/diff/1.sh', str, function (error) {
        if (error) {
            console.log('写入失败')
        } else {
            console.log('写入成功了')
        }
    })
    callfile.execFile('data/diff/1.sh', { shell: 'D:/Git/Git/git-bash.exe' }, function (err, stdout, stderr) {
        if (err) { // 报错返回的结果
            res.send({ code: -1, data: `错误`, msg: err });
            return;
        }
        let file = path.join(__dirname, 'data/diff/diff.txt')   // 保存最终数据的文件
        fs.readFile(file, 'utf-8', function (err, data) {
            if (err) {
                console.log(err)
            } else {
                res.send(data)
                res.end()
            }
        })
    });
})


// 读取issues文件
function getIssues(data, fileDir, lines) {
    // 初始化每一行的错误
    var lineIssues = {}
    for (let i = 0; i < lines; i++) {  // 循环每一行
        lineIssues[i] = { 'CODE_SMELL': [], 'BUG': [], 'VULNERABILITY': [], }
    }
    // 从issues文件中统计哪些行有错误
    var issues = data['issues']
    for (var i = 0; i < issues.length; i++) {
        if (issues[i]['component'].split(':')[1] == fileDir) {  // 是当前文件的问题
            let flows = issues[i]['flows']
            if (flows.length == 0) {
                lineIssues[issues[i]['line']][issues[i]['type']].push([issues[i]['severity'], issues[i]['message'], issues[i]['tags']])
            } else {
                lineIssues[issues[i]['line']][issues[i]['type']].push([issues[i]['severity'], issues[i]['message'], issues[i]['tags']])
                for (let j = 0; j < flows.length; j++) {
                    let locationsArr = flows[j]['locations']  // flows里面的每一个问题数组
                    for (let k = 0; k < locationsArr.length; k++) {
                        lineIssues[locationsArr[k]['textRange']['startLine']][issues[i]['type']].push([issues[i]['severity'], issues[i]['message'], issues[i]['tags']])
                    }
                }
            }
        }
    }
    return lineIssues

    // var issues = data['issues']
    // var issuesRes = { 'CODE_SMELL': { 'BLOCKER': [], 'CRITICAL': [], 'MAJOR': [], 'MINOR': [], 'INFO': [] }, 'BUG': { 'BLOCKER': [], 'CRITICAL': [], 'MAJOR': [], 'MINOR': [], 'INFO': [] }, 'VULNERABILITY': { 'BLOCKER': [], 'CRITICAL': [], 'MAJOR': [], 'MINOR': [], 'INFO': [] } }
    // for(var i=0; i<issues.length; i++){
    //     if(issues[i]['component'].split(':')[1] == fileDir){  // 是当前文件的问题
    //         let flows = issues[i]['flows']
    //         if(flows.length == 0){
    //             issuesRes[issues[i]['type']][issues[i]['severity']].push([issues[i]['line'],issues[i]['message']])
    //         }else{
    //             functionIssue = [issues[i]['line']]  // 出现问题的函数的开始行
    //             for(let j=0; j<flows.length; j++){
    //                 let locationsArr = flows[j]['locations']  // flows里面的每一个问题数组

    //                 for(let k=0;k<locationsArr.length;k++){
    //                     functionIssue.push(locationsArr[k]['textRange']['startLine'])
    //                 }
    //             }
    //             functionIssue.push(issues[i]['message'])
    //             issuesRes[issues[i]['type']][issues[i]['severity']].push(functionIssue)
    //         }
    //     }
    // }
    // return issuesRes
}
app.post("/issuesDt", function (req, res) {
    // app.get("/issuesDt", function (req, res) {
    let fileDir = req.body.fileDir
    let version = req.body.version
    console.log('获取单个文件的issues', fileDir, req.body.version, version)
    let file1 = path.join(__dirname, 'data/source/' + version + '/' + fileDir)
    let file2 = path.join(__dirname, 'data/fileIssues/' + version + '-issues.json')
    // let file1 = path.join(__dirname, 'data/source/transitfeed-1.2.16/feedvalidator.py')
    // let file2 = path.join(__dirname, 'data/fileIssues/transitfeed-1.2.16-issues.json')
    // let fileDir = 'feedvalidator.py'

    fs.readFile(file1, 'utf-8', function (err, data) {
        if (err) {
            console.log(err)
        } else {
            let ress = []
            ress[0] = data
            let lines = data.toString().split('\n').length
            fs.readFile(file2, 'utf-8', function (err, data2) {
                if (err) {
                    console.log(err)
                } else {
                    let tmp = JSON.parse(data2)
                    ress[1] = getIssues(tmp, fileDir, lines)  // 获取当前文件相关的issues
                    res.send(ress)
                    res.end()
                }
            })

        }
    })
})




// 获取两个版本之间的不同issues
app.post("/issuesAddDt", function (req, res) {
    let v1 = req.body.v1.split('--')[1]
    let v2 = req.body.v2.split('--')[1]
    let versionName = ['transitfeed-1.0.7', 'transitfeed-1.0.8', 'transitfeed-1.0.9', 'transitfeed-1.1.0', 'transitfeed-1.1.1',
        'transitfeed-1.1.2', 'transitfeed-1.1.3', 'transitfeed-1.1.4', 'transitfeed-1.1.5', 'transitfeed-1.1.6',
        'transitfeed-1.1.7', 'transitfeed-1.1.8', 'transitfeed-1.1.9', 'transitfeed-1.2.0', 'transitfeed-1.2.1',
        'transitfeed-1.2.2', 'transitfeed-1.2.4', 'transitfeed-1.2.5', 'transitfeed-1.2.6',
        'transitfeed-1.2.7', 'transitfeed-1.2.8', 'transitfeed-1.2.9', 'transitfeed-1.2.10',
        'transitfeed-1.2.11', 'transitfeed-1.2.12', 'transitfeed-github', 'transitfeed-1.2.3',
        'transitfeed-1.2.13', 'transitfeed-1.2.14', 'transitfeed-1.2.15',
        'transitfeed-1.2.16']
    console.log("新增issues", v1, v2)
    let flag = false
    for (var index = 0; index < versionName.length - 1; index++) {
        if (v1 == versionName[index] && v2 == versionName[index + 1]) {   // 表示是前后相邻的版本
            flag = true
            break
        }
    }
    // 只有两个是相邻版本的时候才获取并返回数据
    if (flag == true) {
        let file = path.join(__dirname, 'data/issuesDiff.json')
        fs.readFile(file, 'utf-8', function (err, data) {
            if (err) {
                console.log(err)
            } else {
                let keys = v1 + '&' + v2
                let tmp = JSON.parse(data)
                let ress = tmp[keys]  // 取出当前两个版本下的差异
                let result = []
                for(let k =0;k<ress.length; k++){
                    let filename = ress[k]['component'].split(':')[1]
                    let severityAdd = ress[k]['severity']
                    let line = ress[k]['line']
                    let descirption = ress[k]['message']
                    let tag = ress[k]['type']
                    result.push({'filename':filename, 'line':line, 'severityAdd': severityAdd,'descirption': descirption,  'tag':tag})
                }
                res.send(result)
                res.end()
            }
        })
    }
    else {
        res.send([])
        res.end()
    }
})



// 获取版本的tag
// 数组排序
function unique(arr) {
    return Array.from(new Set(arr))
}
app.post("/tagDt", function(req, res){
    let v1 = req.body.v1
    let v2 = req.body.v2
    if(v2 == ''){
        let file = path.join(__dirname, 'data/tagCollection.json')
        fs.readFile(file, 'utf-8', function (err, data) {
            if (err) {
                console.log(err)
            } else {
                let tmp = JSON.parse(data)
                let ress = tmp[v1]
                res.send(ress)
                res.end()
            }
        })
    }else{
        let file = path.join(__dirname, 'data/tagCollection.json')
        fs.readFile(file, 'utf-8', function (err, data) {
            if (err) {
                console.log(err)
            } else {
                let tmp = JSON.parse(data)
                let tag1 = tmp[v1], tagDict1 = {}
                let tag2 = tmp[v2], tagDict2 = {}
                
                let tagName1 = [], tagName2 = []
                for(let i=0; i<tag1.length; i++){
                    tagName1.push(tag1[i][0])   //  取出第一个版本中的属性值
                    tagDict1[tag1[i][0]] = tag1[i][1]
                }
                for(let j=0; j<tag2.length; j++){
                    tagName2.push(tag2[j][0])   //  取出第二个版本中的属性值
                    tagDict2[tag2[j][0]] = tag2[j][1]
                }


                let allTagName = unique(tagName1.concat(tagName2)).sort()  // 汇总后唯一的tag名称
                let newTag1 = [], newTag2 = []
                for(let k = 0; k<allTagName.length; k++){
                    let value1 = tagDict1[allTagName[k]]? tagDict1[allTagName[k]]: 0
                    let value2 = tagDict2[allTagName[k]]? tagDict2[allTagName[k]]: 0 
                    newTag1.push([allTagName[k], value1])
                    newTag2.push([allTagName[k], value2])
                }


                let ress = {}
                ress['v1'] = newTag1
                ress['v2'] = newTag2
                res.send(ress)
                res.end()
            }
        })
    }
})


// 获取总的统计数据
app.get("/statisticsDt", function(req, res){
    let file = path.join(__dirname, 'data/statistics.json')
    fs.readFile(file, 'utf-8', function(err, data){
        if(err){
            console.log(err)
        }else{
            let tmp = JSON.parse(data)
            let ress= []
            let cate = [], barData = [], rateData = [], rateData1 = []
            for(let i in tmp){
                cate.push(i.split('-')[1])
                barData.push(tmp[i]['ncloc'])
                rateData.push(tmp[i]['files'])
                rateData1.push(tmp[i]['metrics'])
            }
            ress[0] = cate
            ress[1] = barData
            ress[2] = rateData
            ress[3] = rateData1
            res.send(ress)
            res.end()
        }
    })
})