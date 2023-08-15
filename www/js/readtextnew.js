window.onload = async function() {

    let sendData = false;
    ws = new WebSocket("ws://localhost:8000/collection");
    ws.onopen = function(e) 
    {
        console.log("Connected to webgazerExtractServer Collection server");
    };

    ws.onmessage = async function(e) 
    {};

    // let modal = new bootstrap.Modal(document.getElementById('finish_modal'), {});
    const requestIntervalTime = 20;

    document.getElementById('start').addEventListener('click', function(){
        this.disabled = true;
        document.getElementById('finish').disabled = false;
        document.getElementById('results_div').classList.add('d-none')
        let elem_percent = document.getElementById('Results');
        elem_percent.innerHTML = '';
        sendData = true;
    })

    document.getElementById('finish').addEventListener('click', function(){
        document.getElementById('start').disabled = false;
        this.disabled = true;
        try {
            ws.send(JSON.stringify({
                type: "finish",
            }));
            sendData = false;
        }
        catch(err) {
            console.log(err);
        }    
        
    })

    // document.getElementById('close').addEventListener('click', function() {
    //     modal.hide();
    // });

    

    //start the webgazer tracker
    await webgazer.setRegression('ridge') /* currently must set regression and tracker */
        //.setTracker('clmtrackr')
        .setGazeListener(function(data, clock) {
          // console.log(clock);
          if(sendData) {
            let clck = Math.round(clock)
            // if(clck % requestIntervalTime == 0){
              sendMsg(data, clck);
            // }
          }
          
          // console.log(data); /* data is an object containing an x and y key which are the x and y prediction coordinates (no bounds limiting) */
          // console.log(clock); /* elapsed time in milliseconds since webgazer.begin() was called */
        })
        .saveDataAcrossSessions(true)
        .begin();
        webgazer.showVideoPreview(true) /* shows all video previews */
            .showPredictionPoints(true) /* shows a square every 100 milliseconds where current prediction is */
            .applyKalmanFilter(true); /* Kalman Filter defaults to on. Can be toggled by user. */

    //Set up the webgazer video feedback.
    var setup = function() {

        //Set up the main canvas. The main canvas is used to calibrate the webgazer.
        var canvas = document.getElementById("plotting_canvas");
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        canvas.style.position = 'fixed';
    };
    setup();

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
            changeResultData(jdata);
        }
        catch(err){
            console.log("Data not json. Is " + data.data);
        }
    });

    function changeResultData(data){
        let elem_percent = document.getElementById('Results');
        if(data.percentage){
            let percent = Math.round(parseFloat(data.percentage) * 100) / 100;
            elem_percent.innerHTML = percent;    
            document.getElementById('results_div').classList.remove('d-none');
        }
    }

};

// Set to true if you want to save the data even if you reload the page.
window.saveDataAcrossSessions = true;

window.onbeforeunload = function() {
    webgazer.end();
}

/**
 * Restart the calibration process by clearing the local storage and reseting the calibration point
 */
function Restart(){
    document.getElementById("Accuracy").innerHTML = "<a>Not yet Calibrated</a>";
    webgazer.clearData();
    ClearCalibration();
    // PopUpInstruction();
    document.getElementById('readtext').classList.add('d-none');
    document.getElementById('results_div').classList.add('d-none');
    ShowCalibrationPoint();
}
