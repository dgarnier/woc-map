async function getActivites(access_token, num) {

    const activities_link = `https://www.strava.com/api/v3/athlete/activities?access_token=${access_token}:page=1:per_page=${num}`

    var res = await fetch(activities_link)
    var data = await res.json()
    


    async function getActivities()
    fetch(activities_link)
        .then((res) => res.json())
        .then(function (data){


            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }).addTo(map);

            for(var x=0; x<data.length; x++){

                console.log(data[x].map.summary_polyline)
                var coordinates = L.Polyline.fromEncoded(data[x].map.summary_polyline).getLatLngs()
                console.log(coordinates)

                L.polyline(

                    coordinates,
                    {
                        color:"green",
                        weight:5,
                        opacity:.7,
                        lineJoin:'round'
                    }

                ).addTo(map)
            }

        }
        )
}