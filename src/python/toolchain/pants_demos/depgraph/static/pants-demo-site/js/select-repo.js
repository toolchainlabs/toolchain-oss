// Copyright 2023 Toolchain Labs, Inc. All rights reserved.
// Licensed under the Apache License, Version 2.0 (see LICENSE).
const showErrorMessage = function(message) {
    $('.toolchain-info-error-message').text(message)
    $('.toolchain-info-error-message').show()
}

const hideErrorMessage = function() {
    $('.toolchain-info-error-message').hide()
}

const startCloning = function() {
    $('#examining').hide()
    $('#analyzing').hide()
    $('.toolchain-info').hide()
    $('.toolchain-working').show()
    $('#cloning').show()
}

const startExamining = function() {
    $('#cloning').hide()
    $('#analyzing').hide()
    $('.toolchain-info').hide()
    $('.toolchain-working').show()
    $('#examining').show()  
}

const startAnalyzing = function() {
    $('#cloning').hide()
    $('#examining').hide()
    $('.toolchain-info').hide()
    $('.toolchain-working').show()
    $('#analyzing').show()
}

const showResults = function() {
    $('.initial-content').hide()
    $('.data-content').css('display', 'flex')
    $('body').css('background-color', '#F5F5F5')
}

var sendRequest = function() {
    var repoUrl = document.getElementById('repo-input').value

    var myForm = new FormData()
    myForm.append("repo-url", repoUrl)

    fetch(submitUrl, {
        method: "POST",
        body: myForm
            
    }).then(function(res) {
        if(res.status === 400) {
            res.text().then(function(text){
                showErrorMessage(text)
            })
            return
        }

        if(!res.ok) {
            throw new Error()
        }

        res.json().then(function(data){
            window.location.href= data.results_url
        })
    })
    .catch(function(err){
        //ToDo: Handle potential error other than 400
        window.location.assign(window.location.origin + '/error')
    })
}

var setActiveClass = function(el) {
    el.classList.add('active')
  }
  
  var removeActiveClass = function(el) {
    el.classList.remove('active')
  }

var initPopups = function() {
    var whatIsToolchain = document.getElementById('what-is-toolchain');
    var whatIsPants = document.getElementById('what-is-pants');

    var toolchainPopup = document.getElementById('toolchain-popup');
    var pantsPopup = document.getElementById('pants-popup');

    whatIsToolchain.addEventListener('mouseover', function() {
        setActiveClass(toolchainPopup)
    })
    whatIsToolchain.addEventListener('mouseout', function() {
        removeActiveClass(toolchainPopup)
    })

    whatIsPants.addEventListener('mouseover', function() {
        setActiveClass(pantsPopup)
    })
    whatIsPants.addEventListener('mouseout', function() {
        removeActiveClass(pantsPopup)
    })
}

window.addEventListener('load', function(){
    var form = document.getElementById('repo-url-form')
    if(form) {
        form.addEventListener('submit', function(e){
            e.preventDefault()
            sendRequest()
        })
    }


    initPopups()
})

//Show Examples Logic

window.addEventListener('load', function(){
    var seeExamplesBtn = document.getElementById('see-examples')
    var goBackBtn = document.getElementById('go-back')
    var initialContent = document.getElementById('initial-content')
    var examplesContent = document.getElementById('examples-content')

    if(!seeExamplesBtn || !initialContent || !examplesContent || !goBackBtn) {
        return
    }

    setActiveClass(initialContent)

    seeExamplesBtn.addEventListener('click', function() {
        setActiveClass(examplesContent)
        removeActiveClass(initialContent)
    })

    goBackBtn.addEventListener('click', function() {
        setActiveClass(initialContent)
        removeActiveClass(examplesContent)
    })

})

var showExamples = false;

/* Google Analytics  */
window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', 'G-4HE7GWGBHB');