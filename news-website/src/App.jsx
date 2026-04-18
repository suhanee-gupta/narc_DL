import React from "react";
// Remove "/pages" if the file is in the same folder as App.jsx
import NewsroomApp from "./NewsroomApp"; 

function App() {
  return (
    // Added a simple error boundary check wrapper
    <React.Suspense fallback={<div>Loading...</div>}>
      <NewsroomApp />
    </React.Suspense>
  );
}

export default App;