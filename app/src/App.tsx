import { JSX } from "react"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import { routes } from "./routes"

function App(): JSX.Element {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <main className="w-full h-screen py-6 px-4 flex items-center justify-center">
          <Routes>
            {routes.map(route => (
              <Route
                key={route.path}
                path={route.path}
                element={route.element}
              />
            ))}
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
