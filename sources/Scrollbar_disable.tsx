import * as React from "react"
import { addPropertyControls, ControlType } from "framer"
/**
 * @framerDisableUnlink
 */
export function GlobalScrollbarHider({ forceHide }) {
    React.useLayoutEffect(() => {
        if (!forceHide) return

        const styleId = "global-scrollbar-hider-style"
        if (document.getElementById(styleId)) return

        const style = document.createElement("style")
        style.id = styleId
        style.innerHTML = `
            .lenis {
                scrollbar-width: none;
                -ms-overflow-style: none;
            }

            .lenis::-webkit-scrollbar {
                display: none;
                width: 0 !important;
                height: 0 !important;
                background: transparent;
            }

            * {
                scrollbar-width: none !important;
                -ms-overflow-style: none !important;
            }

            *::-webkit-scrollbar {
                display: none !important;
                width: 0px !important;
                height: 0px !important;
                background: transparent !important;
            }
        `
        document.head.appendChild(style)

        return () => {
            const existing = document.getElementById(styleId)
            if (existing) document.head.removeChild(existing)
        }
    }, [forceHide])

    // When forceHide is false, truly render nothing — no DOM, no effects
    if (!forceHide) return <></>

    // When active, render minimal hidden node for Framer Canvas
    return <div style={{ display: "none" }} />
}

GlobalScrollbarHider.defaultProps = {
    forceHide: true,
}

GlobalScrollbarHider.displayName = "Scrollbar Hider"

addPropertyControls(GlobalScrollbarHider, {
    forceHide: {
        type: ControlType.Boolean,
        title: "Hide",
        defaultValue: true,
        description: "Hides all scrollbars on the page it is added to.",
    },
})
