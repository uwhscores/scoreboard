uwhScoresUser = function(){
  // day filter on the schedule
  document.querySelectorAll('.toggleDay').forEach( el => {
    el.addEventListener('click', function(event){
      var dayFilter = event.currentTarget.getAttribute('day');

      var activeButtons = document.querySelectorAll('#dayPager .active')
      activeButtons.forEach( i => i.classList.remove('active'))
      event.currentTarget.classList.add('active')

      var rows = document.querySelectorAll("#games tr")
      if ( dayFilter == "All"){
        rows.forEach( i => {i.hidden = false})
      } else  {
        rows.forEach( i => {
          rowsDay = i.getAttribute("day")
          if (rowsDay == null) {
            return
          }
          if (rowsDay === dayFilter) {
            i.hidden = false
          } else {
            i.hidden = true
          }
        })
      }
    })
  });

  // playerr search page
  var playerSearch = document.getElementById('playerSearch')
  if (playerSearch) {
      playerSearch.addEventListener("submit", function(event) {
      console.log("searching")
      event.preventDefault()
      if (document.getElementById('search-box').value.length > 2 ){
        var searchString = document.getElementById('search-box').value
        var playerList = document.getElementById('players')
        playerList.innerHTML = null
        fetch(`/cgi/search?entity=players&like=${searchString}`)
        .then(response => {
          if (!response.ok) { throw response }
          return response.json()
        })
        .then(data => {
          results = data["results"]
          if (results.length > 0){
            console.log(results)
            results.forEach(p => {
              var li = document.createElement('a');
              li.setAttribute('href', `/p/${p['player_id']}`)
              li.classList.add("list-group-item")
              li.classList.add("list-group-item-action")
              li.appendChild(document.createTextNode(p['display_name']));
              playerList.appendChild(li);
            })
          } else {
            // no matches
            console.log("No matches")
          }

        })
        .catch(error => {
          error.json().then( message => {
              console.error(message)
            })
        })
      }
    })
  };
}();
