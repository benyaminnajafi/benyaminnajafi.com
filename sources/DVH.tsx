import type { ComponentType } from "react"

export const DynamicHeight = (Component: ComponentType): ComponentType => {
    return (props) => {
        return (
            <Component
                {...props}
                style={{
                    ...props.style,
                    height: "100dvh", // dvh — Dynamic Viewport Height is a relative unit that adapts to UI visibility on mobile
                }}
            />
        )
    }
}
