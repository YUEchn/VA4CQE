### introduction
VA4CQE is a visual analytics system for software project quality evolution

![Example Image](/VA4CQE.png)``

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
