import { Toaster as Sonner } from "sonner"

type ToasterProps = React.ComponentProps<typeof Sonner>

const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="dark"
      className="toaster group"
      toastOptions={{
        classNames: {
          toast:
            "group toast group-[.toaster]:bg-secondary group-[.toaster]:text-foreground group-[.toaster]:border-border group-[.toaster]:shadow-lg",
          description: "group-[.toast]:text-muted-foreground",
          actionButton:
            "group-[.toast]:bg-burnt group-[.toast]:text-white",
          cancelButton:
            "group-[.toast]:bg-accent group-[.toast]:text-muted-foreground",
          error: "group-[.toaster]:bg-red-900/50 group-[.toaster]:border-red-800",
          success: "group-[.toaster]:bg-green-900/50 group-[.toaster]:border-green-800",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
