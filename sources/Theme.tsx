import { useLayoutEffect } from "react"
import { createStore } from "https://framer.com/m/framer/store.js@^1.0.0"
import type { Override } from "framer"

const isBrowser =
    typeof window !== "undefined" && typeof document !== "undefined"

const getInitialTheme = () =>
    isBrowser ? localStorage.getItem("theme") || "system" : "system"

const useStore = createStore({
    theme: getInitialTheme(),
})

const applyTheme = (theme: string) => {
    if (!isBrowser) return

    const html = document.documentElement
    const body = document.body

    html.setAttribute("toggle-theme", theme)
    body.setAttribute("toggle-theme", theme)
    localStorage.setItem("theme", theme)
    window.dispatchEvent(new Event("themeChange"))
}

export function useSingleToggle(): Override {
    const [store, setStore] = useStore()

    useLayoutEffect(() => {
        if (!isBrowser) return

        let themeToApply = store.theme

        // PRIORITY LOAD: Scroll into view & eager load
        const el = document.querySelector('[data-framer-name="Theme Toggle"]')
        if (el) {
            // Helps load above-the-fold element quickly
            el.setAttribute("loading", "eager")
            el.setAttribute("fetchpriority", "high")
            el.scrollIntoView({ block: "center", inline: "center" })
        }

        if (themeToApply === "system") {
            const mq = window.matchMedia("(prefers-color-scheme: dark)")
            themeToApply = mq.matches ? "dark" : "light"
            setStore({ theme: themeToApply })
            localStorage.setItem("theme", themeToApply)
        }

        applyTheme(themeToApply)

        let lightTokens: string[] = []
        let darkTokens: string[] = []

        for (const sheet of document.styleSheets) {
            try {
                for (const rule of sheet.cssRules) {
                    if (
                        "selectorText" in rule &&
                        rule.selectorText === "body"
                    ) {
                        for (let i = 0; i < rule.style.length; i++) {
                            const name = rule.style[i]
                            if (name.includes("--token")) {
                                const value = rule.style.getPropertyValue(name)
                                lightTokens.push(`${name}: ${value};`)
                            }
                        }
                    }
                    if (
                        "conditionText" in rule &&
                        rule.conditionText.includes(
                            "prefers-color-scheme: dark"
                        )
                    ) {
                        const css = rule.cssRules?.[0]?.cssText ?? ""
                        darkTokens = css
                            .replace("body", "")
                            .replace(/{|}/g, "")
                            .split(";")
                            .map((s) => s.trim() + ";")
                            .filter(Boolean)
                    }
                }
            } catch {
                // skip CORS-protected stylesheets
            }
        }

        document.getElementById("toggle-theme")?.remove()

        const style = document.createElement("style")
        style.id = "toggle-theme"
        style.textContent = `
            body[toggle-theme="light"] { ${lightTokens.join(" ")} }
            body[toggle-theme="dark"]  { ${darkTokens.join(" ")} }
            html[toggle-theme="light"] { color-scheme: light; }
            html[toggle-theme="dark"]  { color-scheme: dark; }
        `
        document.head.appendChild(style)

        return () => {
            document.getElementById("toggle-theme")?.remove()
            applyTheme("system")
        }
    }, [store.theme])

    const handleClick = () => {
        const newTheme = store.theme === "light" ? "dark" : "light"
        setStore({ theme: newTheme })
        applyTheme(newTheme)
    }

    return {
        onClick: handleClick,
        variant: store.theme === "light" ? "Light" : "Dark",
        role: "button",
        "aria-pressed": store.theme === "dark",
    }
}
