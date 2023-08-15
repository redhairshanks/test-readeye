window.saveDataAcrossSessions = false;
const requestIntervalTime = 20;
var webgazerCanvas = null;

window.onload = async function() {

    ws = new WebSocket("ws://localhost:8000/collection");
    ws.onopen = function(e) 
    {
        console.log("Connected to webgazerExtractServer Collection server");
    };

    const requestIntervalTime = 20;

    let modal = new bootstrap.Modal(document.getElementById('finish_modal'), {});
    let toast = new bootstrap.Toast(document.getElementById('toast'), {});

    async function startWebGazer() {
        if (!window.saveDataAcrossSessions) {
            var localstorageDataLabel = 'webgazerGlobalData';
            localforage.setItem(localstorageDataLabel, null);
            var localstorageSettingsLabel = 'webgazerGlobalSettings';
            localforage.setItem(localstorageSettingsLabel, null);
        }
        const webgazerInstance = await webgazer.setRegression('ridge') /* currently must set regression and tracker */
          .setTracker('TFFacemesh')
          .begin();
        webgazerInstance.showVideoPreview(true) /* shows all video previews */
          .showPredictionPoints(true) /* shows a square every 100 milliseconds where current prediction is */
          .applyKalmanFilter(true); // Kalman Filter defaults to on.
          // Add the SVG component on the top of everything.
        webgazer.setGazeListener( readTextListener );
    }

    //start the webgazer tracker
    document.getElementById('start').addEventListener('click', function(){
        startWebGazer();
    })

    document.getElementById('finish').addEventListener('click', function(){
        try {
            ws.send(JSON.stringify({
                type: "finish"
            }))
            webgazer.end();
        }
        catch(err) {
            console.log(err)
            toast.show();
        }    
        
    })

    document.getElementById('close').addEventListener('click', function() {
        modal.hide();
    })

    async function sendMsg(msg, clock) {
        let picked = {};
        if(msg){
            picked = (({ x, y }) => ({ x, y }))(msg);
            picked["clock"] = clock;
            picked["type"] = "readtext"
            console.log(picked);
        }
        if(picked){
            ws.send(JSON.stringify(picked));
        }
    }

    ws.addEventListener("message", function incoming(data) {
        console.log(data.data);
        let jdata = null;
        try {
            jdata = JSON.parse(data.data);
            changeModalData(jdata);
        }
        catch(err){
            console.log("Data not json. Is " + data.data);
        }
    });

    function changeModalData(data){
        let elem_percent = document.getElementById('percentage');
        if(data.percentage){
            elem_percent.innerHTML = data.percentage;    
            modal.show();
        }
    }

};

window.onbeforeunload = function() {
    if (window.saveDataAcrossSessions) {
        webgazer.end();
    } else {
        localforage.clear();
    }
  }

var readTextListener = async function(data, clock) {
    if(!data)
      return;

    console.log('x, y coordinates');
    console.log(data);
    let clck = Math.round(clock)
    if(clck % requestIntervalTime == 0){
      sendMsg(data, clck);
    }

    if (!webgazerCanvas) {
      webgazerCanvas = webgazer.getVideoElementCanvas();
    }

    async function sendMsg(msg, clock) {

        let picked = {};
        if(msg){
            picked = (({ x, y }) => ({ x, y }))(msg);
            picked["clock"] = clock;
            picked["type"] = "readtext"
            console.log(picked);
        }
        if(picked){
            ws.send(JSON.stringify(picked));
        }
    }      
}

