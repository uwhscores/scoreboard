uwhScoresAdmin = function(){
  // tournament admin page
  async function updateTournamentConfig(config_name, config){
      // helper function to make the PUT call to update tournament config parameter
      // returns the response JSON if 200
      let put_json = {}
      put_json['config_name'] = config_name
      put_json[config_name] = config
      if (! tournamentShortName) {
        console.error("Tournament shotname undefined, cannot make update call")
        throw("Tournament shotname undefined, cannot make update call")
      }
      const respond = await fetch(`/admin/t/${tournamentShortName}`, {
        method: "PUT",
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(put_json)
      })
      .then(response => {
        if (!response.ok) { throw response }
        return response
      })
      .then(response => response.json())
      .catch( error => {
        try {
          error.json().then( message => {
            //Here is already the payload from API
            if (message['message']) {
              console.error("UWHScores API Error:", message)
              window.alert(message['message'])
            } else {
              throw(message)
            }
          })
        } catch(e) {
          console.error("Unkown Error:", e)
        }
      })
      return respond
  };

  // update tournament banner
  var banner_update_button = document.getElementById('bannerUpdateButton')
  if (banner_update_button) {
    banner_update_button.addEventListener("click", function(event) {
      let enabled_check = document.getElementById('bannerEnable').checked
      let banner_text = document.getElementById('bannerText').value

      let banner = {'enabled': enabled_check, 'message': banner_text}
      updateTournamentConfig("banner", banner)
      .then(data => {
        if ( data['success'] ) {
          document.getElementById('bannerPreview').hidden = ! data['config']['enabled']
          document.getElementById('bannerPreviewText').innerText = data['config']['message']
        }
      })
    })
  };

  // update tournament blackout
  var blackout_update_button = document.getElementById('blackoutUpdateButton')
  if (blackout_update_button) {
    blackout_update_button.addEventListener("click", function(event) {
      let blackout_check = document.getElementById('blackoutEnable').checked
      let blackout_text = document.getElementById('blackoutText').value

      let blackout = {'enabled': blackout_check, 'message': blackout_text}
      updateTournamentConfig("blackout", blackout)
      .then(data => {
        if ( data['success'] ) {
          document.getElementById('blackoutPreview').hidden = ! data['config']['enabled']
          document.getElementById('blackoutPreviewText').innerText = data['config']['message']
          document.getElementById('blackoutWarning').hidden = !data['config']['enabled']
        }
      })
    })
  };

  // activte/deactive user as tournament admin
  var adminUserRows = document.querySelectorAll('.active-admin, .inactive-admin')
  adminUserRows.forEach( el => {
    el.addEventListener('click', function(e) {
      const curEl = e.currentTarget
      const userId = curEl.getAttribute('user-id')
      const parentId = curEl.parentElement.id
      //  baseed on what list the  user is on, flip the admin status
      if (parentId == "activeAdminsList") {
        makeAdmin = false
      } else if (parentId == "inactiveAdminsList") {
        makeAdmin = true
      } else {
        // something is wrong
        return
      }
      let admin = {'make_admin': makeAdmin, 'user_id': userId}
      updateTournamentConfig("admin", admin)
      .then(response => {
        if ( response['success'] ) {
          const active_list = document.getElementById("activeAdminsList")
          const inactive_list = document.getElementById("inactiveAdminsList")
          curEl.classList.add("list-group-item-info")
          let childEl = curEl.children[0]
          if (makeAdmin) {
            childEl.classList.remove("bi-plus-circle")
            childEl.classList.add("bi-dash-circle")
            active_list.insertBefore(curEl, active_list.childNodes[0])
          } else {
            childEl.classList.remove("bi-dash-circle")
            childEl.classList.add("bi-plus-circle")
            inactive_list.insertBefore(curEl, inactive_list.childNodes[0])
          }
        }
      })
    })
  });

  // tie submit
  document.querySelectorAll('.tieSubmitBtn').forEach( el => {
    var tieFormEl = document.getElementById(el.getAttribute('submit-for'))
    tieFormEl.addEventListener('submit', function(){
      event.preventDefault()
      let tieId = event.currentTarget.getAttribute('tie-id')
      const radioId = `radio-${tieId}`
      const modalId = `tieModal-${tieId}`
      var teamList = []
      document.querySelectorAll(`input[name="${radioId}"]`).forEach( t => {
        teamList.push(parseInt(t.value, 10))
      })
      let winner = document.querySelector(`input[name="${radioId}"]:checked`);
      if ( winner ) {
        winner_id = parseInt(winner.value, 10)
        let tie = {'teams': teamList, 'winner': winner_id}
        updateTournamentConfig("tie_break", tie)
        .then(data => {
          if ( data['success'] ) {
            let tieModal = bootstrap.Modal.getInstance(document.getElementById(modalId))
            tieModal.hide()
            tieModal.dispose()
            let el = document.getElementById(`tie-${tieId}`)
            el.hidden = true
          }
        })
      }
    })
  });

  // finalize tournament
  var finalizeSubmitBtn = document.getElementById('finalizeSubmitBtn')
  if (finalizeSubmitBtn) {
    finalizeSubmitBtn.addEventListener("click", function(event) {
      let finalize = {'finalize': true}
      updateTournamentConfig("finalize", finalize)
      .then(response => {
        if ( response['success'] ){
          window.location.replace("/admin")
        }
      })
    })
  };

  // timing rule pages
  var showTimingJsonBtn = document.getElementById('showTimingJsonBtn')
  if (showTimingJsonBtn) {
    showTimingJsonBtn.addEventListener("click", function(event) {
      const tid = event.currentTarget.getAttribute('tid')
      let rawTimingJson = document.getElementById('rawTimingJson')
      if (rawTimingJson.innerText == ""){
        fetch(`/api/v1/tournaments/${tid}/timingruleset`)
        .then(response => {
          if (!response.ok) { throw response }
          return response.json()
        })
        .then(data => {
          rawTimingJson.innerText =  JSON.stringify(data, null, 2)
        })
        .catch(error => {
          let rawTimingJson = document.getElementById('rawTimingJson')
          rawTimingJson.innerText = "--- Error fetching JSON ---"
          rawTimingJson.hidden = ! rawTimingJson.hidden
        })
      }
      rawTimingJson.hidden = ! rawTimingJson.hidden
    })
  };

  // set the text in the raw json editing box back to the currently configured value via API
  function refreshTimingJsonBox(){
      var timingJsonBox = document.getElementById('timingJsonBox')
      const tid = timingJsonBox.getAttribute('tid')
      document.getElementById("timingJsonError").hidden = true
      fetch(`/api/v1/tournaments/${tid}/timingruleset`)
      .then(response => {
        if (!response.ok) { throw response }
        return response.json()
      })
      .then(data => {
        timingJsonBox.value =  JSON.stringify(data, null, 2)
      })
      .catch(error => {
        timingJsonBox.value = "--- Error fetching JSON ---"
      })
    };

  // populate the box on first load
  if (document.getElementById('timingJsonBox')) {
    refreshTimingJsonBox()
  };

  // timing rules json text box reset by user
  var editTimingResetBtn = document.getElementById('editTimingResetBtn')
  if (editTimingResetBtn) {
    editTimingResetBtn.addEventListener('click', function() { refreshTimingJsonBox() })
  };

  // timing ruleees json submit changes
  var editTimingSaveBtn = document.getElementById('editTimingSaveBtn')
  if (editTimingSaveBtn) {
    editTimingSaveBtn.addEventListener('click', function() {
      var timingJsonBox = document.getElementById('timingJsonBox')
      const tid = timingJsonBox.getAttribute('tid')
      try {
        var timingJson = JSON.parse(timingJsonBox.value)
      } catch(e) {
        document.getElementById("timingJsonError").hidden = false
        console.error("Invalid JSON", e)
        return
      }
      updateTournamentConfig("timing_rules", timingJson)
      .then(data => {
        if ( data['success'] ) {
          window.location.replace(`/admin/t/${tournamentShortName}/gametiming`)
        }
      })
    })
  };

  // handle new user create modal from /admin/users
  var createUserForm = document.getElementById('createUserForm')
  if (createUserForm) {
    createUserForm.addEventListener("submit", function(event) {
      event.preventDefault()
      let createModal = bootstrap.Modal.getInstance(document.getElementById('createUserModal'))

      // need to turn the new user modal into a modal since there is no button
      // on the page that does it automatically
      let newUserModal = new bootstrap.Modal(document.getElementById('newUserModal'), null)
      let createForm = document.getElementById('createUserForm');

      let newUser = {'email': createForm.email.value,
                     'short_name': createForm.shortName.value,
                     'admin': createForm.isAdmin.checked
                   };

      fetch('/admin/users', {
        method: "POST",
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({'user': newUser})
      })
      .then(response => response.json())
      .then(data => {
        if (! data['success']) {
          throw data['message']
        }
        user = data['user']
        let title = document.getElementById('newUserModalLabel')
        title.innerText = `New User ${user['short_name']} Created`
        let link = document.getElementById('newTokenLink')
        link.href=`${window.location.origin}/login/reset?token=${user['token']}`
        link.text=`${window.location.origin}/login/reset?token=${user['token']}`

        createModal.hide()
        newUserModal.show()
      })
      .catch((error) => {
        console.error('Error:', error);
      })
    })
  }

  // handle /admin/users user admin toggle
  var adminToggles = document.querySelectorAll('.admin-toggle')
  adminToggles.forEach( el => {
    el.addEventListener('click', function() {
      let users_toggle = event.currentTarget
      is_admin = users_toggle.checked
      let user_id = users_toggle.getAttribute('user-id')
      fetch(`/admin/users/${user_id}`, {
        method: "PUT",
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({'user': {'user_id': user_id, 'admin': is_admin}})
      })
      .then(response => response.json())
      .then(result => {
        console.log('Success:', result);
      })
      .catch(error => {
        console.error('Error:', error);
      })
    })
  });

  // handle /admin/users user active toggle
  var activeToggles = document.querySelectorAll('.active-toggle')
  activeToggles.forEach( el => {
    el.addEventListener('click', function(){
      let users_toggle = event.currentTarget
      is_active = users_toggle.checked
      let user_id = users_toggle.getAttribute('user-id')
      fetch(`/admin/users/${user_id}`, {
        method: "PUT",
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({'user': {'user_id': user_id, 'active': is_active}})
      })
      .then(response => response.json())
      .then(result => {
        console.log('Success:', result);
      })
      .catch(error => {
        console.error('Error:', error);
      })
    })
  });

  //handle /admin/users reset user password
  // show reset modal
  var resetPasswordModal = document.getElementById('resetPasswordModal')
  if (resetPasswordModal) {
    resetPasswordModal.addEventListener('show.bs.modal', function(event) {
      let caller_button = event.relatedTarget
      // Extract info from data-bs-* attributes
      let user_id = caller_button.getAttribute('user-id')
      let continue_button = document.getElementById('resetPasswordContinue')
      continue_button.setAttribute("user-id", user_id)
    })
  };

  // submit user password reset request
  var passwordResetConfirm = document.getElementById('resetPasswordContinue')
  if (passwordResetConfirm) {
    passwordResetConfirm.addEventListener('click', function() {
      let continue_button = document.getElementById('resetPasswordContinue')
      let user_id = continue_button.getAttribute('user-id')

      let resetModal = bootstrap.Modal.getInstance(document.getElementById('resetPasswordModal'))
      let newUserModal = new bootstrap.Modal(document.getElementById('newUserModal'), null)

      fetch(`/admin/users/${user_id}`, {
        method: "PUT",
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({'user': {'user_id': user_id, 'reset_password': true}})
      })
      .then(response => response.json())
      .then(result => {
        let modalTitle = document.getElementById('newUserModalLabel')
        modalTitle.innerText = "Password Succesfully Reset"
        let messageHeader = document.getElementById('newUserHeader')
        messageHeader.innerText = 'Your Password has Been Reset'
        let link = document.getElementById('newTokenLink')
        link.href=`${window.location.origin}/login/reset?token=${result['token']}`
        link.text=`${window.location.origin}/login/reset?token=${result['token']}`

        resetModal.hide()
        newUserModal.show()
      })
      .catch(error => {
        console.error('Error:', error);
      })
    })
  };

  // Score input page
  // handle up/down buttons for score input
  document.querySelectorAll(".score-input-button").forEach( el => {
    el.addEventListener('click', function(event){
      let score_id = event.currentTarget.getAttribute('update-for')
      let direction = event.currentTarget.getAttribute('direction')
      let net = 0
      if (direction === "up"){
        net = 1
      } else {
        net = -1
      }
      let new_score = parseInt(document.getElementById(score_id).innerText, 10) + net
      if (new_score > 0) {
        document.getElementById(score_id).innerText = new_score
      } else {
        document.getElementById(score_id).innerText = 0
      }
    })
  });

  // submit score
  var scoreSubmitBtn = document.getElementById("scoreSubmitBttn")
  if (scoreSubmitBtn) {
    scoreSubmitBtn.addEventListener('click', function() {
      let score_w = parseInt(document.getElementById('score_w').innerText, 10)
      let score_b = parseInt(document.getElementById('score_b').innerText, 10)
      let forfeit_w = document.getElementById('forfeit_w').checked
      let forfeit_b = document.getElementById('forfeit_b').checked

      let score = {
        'score_w': score_w,
        'score_b': score_b,
        'forfeit_w': forfeit_w,
        'forfeit_b': forfeit_b
      }
      fetch(window.location.href, {
        method: "PUT",
        headers: {
          'Content-Type': 'application/json'
        },
        redirect: "follow",
        body: JSON.stringify({'score': score})
      })
      .then(response => response.json())
      .then(result => {
        if (result['success'] ) {
          window.location.href = result['url'];
        }
      })
      .catch(error => {
        console.error('Error:', error);
      })
    })
  };

  // player pages
  // toggle editor view
  var togglePlayedButton = document.getElementById('togglePlayed')
  if (togglePlayedButton) {
    togglePlayedButton.addEventListener('click', function(event) {
      let current_display = (togglePlayedButton.getAttribute('value') == 'true')
      document.querySelectorAll('.played').forEach(function(el) {
        if  (current_display) {
          el.style.removeProperty('display')
        } else {
          el.style.display = "None"
        }
      });
      let new_icon = document.createElement("i")
      new_icon.classList.add("px-1")
      if (current_display) {
        togglePlayedButton.setAttribute("value", "false")
        togglePlayedButton.textContent = "Hide Played Games"
        new_icon.classList.add("bi", "bi-funnel-fill")
        togglePlayedButton.prepend(new_icon)
      }  else {
        togglePlayedButton.setAttribute("value", "true")
        togglePlayedButton.textContent = "Show Played Games"
        new_icon.classList.add("bi", "bi-funnel")
        togglePlayedButton.prepend(new_icon)
      }
    })
  };

  // submit player changes
  var game_rows = document.querySelectorAll('.game-row')
  game_rows.forEach(el => {
    var gid = el.getAttribute('gid')
    if (gid) {
      el.addEventListener('click', function(e) {
        window.location.href = `${window.location.href}/${gid}`
      })
    }
  });


  // player management page
  function togglePlayerEdit(){
    document.querySelectorAll('.view-player').forEach(function(el) {
      el.hidden = ! el.hidden
    })
    document.querySelectorAll('.edit-player').forEach(function(el) {
      el.hidden = ! el.hidden
    })
  };

  document.querySelectorAll('.player-edit-toggle').forEach( function(el) {
    el.addEventListener('click', function() { togglePlayerEdit()})
  });

  var playerSaveBtn = document.getElementById('playerSaveBtn')
  if (playerSaveBtn) {
    playerSaveBtn.addEventListener('click', function() {
      var displayName = document.getElementById("inputDisplayName").value
      if (! displayName) {
        console.error("Couldn't find player name")
        return
      }
      var player = {'display_name': displayName, 'player_id': playerId}
      fetch(window.location.href, {
        method: "PUT",
        headers: {
          'Content-Type': 'application/json'
        },
        redirect: "follow",
        body: JSON.stringify({'player': player})
      })
      .then(response => {
        if (!response.ok) { throw response }
        return response.json()
      })
      .then(result => {
        if (result['success'] ) {
          document.getElementById("playerDisplayName").innerText = displayName
          togglePlayerEdit()
        }
      })
      .catch(error => {
        var errorMessage = "There was an issue updating the player"
        var errorEl = document.getElementById("errorMsg")
        error.json().then( message => {
          if (message['message']) {
            errorMessage = message['message']
          } else {
            console.error(message)
          }
          errorEl.innerText = errorMessage
          errorEl.hidden = false
        })
      })
    })
  };
}();
