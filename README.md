### introduction
VA4CQE is a visual analytics system for software project quality evolution.

![Example Image](/VA4CQE.png)

The system contains three parts. One is the project feature overview view, quality evolution view and file issues view; the second is the top tags view and version radar tree view in non-comparison mode; and the third is the tags comparison view, version differences view, list of added issues and version comparison radar tree view in comparison mode.

The system provides a macro overview of the project's development process, analysing its evolutionary characteristics and identifying important time points in the development process; it also explores individual releases in detail, capturing important information within the release.

[Demo Link](https://youtu.be/vCWHlrgteV4)

#### project directory
```
vis_repo
|-- back
|   |-- data (example data)
|   |-- server.js (Backend based on node.js)
|-- vis
    |-- static
    |-- config 
    |-- src (functional component)
        |-- assets
        |-- router 
        |-- store (global variables)
        |-- App.vue (mian file)
        |-- main.js
        |-- components (modules implementation)
        |   |-- center
        |   |-- left
        |   |-- right
```
### develop environment preparation
- install dependencies

In the VA4CQE/back directory, run: `npm install`

In the VA4CQE/vis directory, run: `npm install`

### start it

- start backend(VA4CQE/back), run: `npm start`

- start frontend(VA4CQE/vis), run: `npm run dev`

- check the status of VA4CQE：`http://x.x.x.x:8081`
