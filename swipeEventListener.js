document.addEventListener(
    'keydown',
    function keyDownHandler(event) {
        const keyActionsMap = {
            'Enter': 'superlike',
            'ArrowLeft': 'dislike',
            'ArrowRight': 'like',
            // [1] Edge (16 and earlier) and Firefox (36 and earlier) use "Left", "Right", "Up", and "Down" instead of "ArrowLeft", "ArrowRight", "ArrowUp", and "ArrowDown"
            'Left': 'dislike',
            'Right': 'like',
        }

        const action = keyActionsMap[event.key];
        console.log(`${event.key} was pressed, mapped action: ${action}`);

        if ( action !== undefined && action !== null ) {
            console.log(`Triggering ${action} event`);

            var eventDiv = document.createElement('div');

            eventDiv.className = 'userSwipeAction';
            eventDiv.setAttribute('value', action);
            eventDiv.style.display = 'none';

            document.body.appendChild(eventDiv);
        }
    }
);