import React, { useState, useRef, useEffect } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileId, setFileId] = useState("");
  const [imageUrl, setImageUrl] = useState("");
  const [boxes, setBoxes] = useState([]);
  const [report, setReport] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState("");
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [currentStep, setCurrentStep] = useState(0);
  const [debugMode, setDebugMode] = useState(false);
  const imageRef = useRef();

  // Handle window resize to recalculate bounding box positions
  useEffect(() => {
    const handleResize = () => {
      if (boxes.length > 0 && imageRef.current) {
        // Force re-render of bounding boxes on resize
        setTimeout(() => {
          setBoxes(prev => [...prev]);
        }, 100);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [boxes.length]);

  // Progress steps
  const steps = [
    { id: 1, label: "Upload DICOM", completed: !!fileId, active: currentStep === 1 },
    { id: 2, label: "Detect Pathologies", completed: boxes.length > 0, active: currentStep === 2 },
    { id: 3, label: "Generate Report", completed: !!report, active: currentStep === 3 }
  ];

  // Clear all states
  const resetAll = () => {
    setFileId("");
    setImageUrl("");
    setBoxes([]);
    setReport("");
    setError("");
    setSuccessMessage("");
    setCurrentStep(0);
  };

  // Handle file selection
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setSelectedFile(file);
    resetAll();
    if (file) {
      setSuccessMessage(`Selected: ${file.name}`);
      setTimeout(() => setSuccessMessage(""), 3000);
    }
  };

  // Upload DICOM file
  const handleUpload = async () => {
    if (!selectedFile) return;
    setLoading(true);
    setLoadingStep("Uploading and converting DICOM file...");
    setCurrentStep(1);
    setError("");
    setSuccessMessage("");
    setBoxes([]);
    setReport("");
    
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const res = await fetch(`${API_URL}/upload/`, {
        method: "POST",
        body: formData,
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Upload failed");
      }
      
      const data = await res.json();
      setFileId(data.file_id);
      setImageUrl(`${API_URL}${data.png_url}`);
      setSuccessMessage("DICOM file uploaded and converted successfully!");
      setCurrentStep(0);
      
      setTimeout(() => setSuccessMessage(""), 3000);
    } catch (err) {
      setError(err.message || "Upload failed. Please try again.");
      setCurrentStep(0);
    } finally {
      setLoading(false);
      setLoadingStep("");
    }
  };

  // Predict bounding boxes
  const handlePredict = async () => {
    if (!fileId) return;
    setLoading(true);
    setLoadingStep("Analyzing X-ray for pathologies...");
    setCurrentStep(2);
    setError("");
    setSuccessMessage("");
    setBoxes([]);
    setReport("");
    
    try {
      const params = new URLSearchParams({ file_id: fileId });
      const res = await fetch(`${API_URL}/predict/?${params.toString()}`, {
        method: "POST",
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Prediction failed");
      }
      
      const data = await res.json();
      const preds = data.annotations?.predictions || [];
      setBoxes(preds);
      
      if (preds.length > 0) {
        setSuccessMessage(`Found ${preds.length} potential patholog${preds.length === 1 ? 'y' : 'ies'}!`);
      } else {
        setSuccessMessage("No pathologies detected in this X-ray.");
      }
      setCurrentStep(0);
      
      setTimeout(() => setSuccessMessage(""), 3000);
    } catch (err) {
      setError(err.message || "Prediction failed. Please try again.");
      setCurrentStep(0);
    } finally {
      setLoading(false);
      setLoadingStep("");
    }
  };

  // Generate LLM report
  const handleReport = async () => {
    if (!fileId) return;
    setLoading(true);
    setLoadingStep("Generating diagnostic report...");
    setCurrentStep(3);
    setError("");
    setSuccessMessage("");
    setReport("");
    
    try {
      const params = new URLSearchParams({ file_id: fileId });
      const res = await fetch(`${API_URL}/report/?${params.toString()}`, {
        method: "POST" 
      });
      
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Report generation failed");
      }
      
      const data = await res.json();
      setReport(data.report);
      setSuccessMessage("Diagnostic report generated successfully!");
      setCurrentStep(0);
      
      setTimeout(() => setSuccessMessage(""), 3000);
    } catch (err) {
      setError(err.message || "Report generation failed. Please try again.");
      setCurrentStep(0);
    } finally {
      setLoading(false);
      setLoadingStep("");
    }
  };

  // Draw bounding boxes on image
  const renderBoxes = () => {
    if (!boxes.length || !imageRef.current) return null;
    const img = imageRef.current;
    const container = img.parentElement;
    
    // Get the actual rendered dimensions and position of the image
    const imgRect = img.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    
    // Calculate the offset of the image within its container
    const offsetX = imgRect.left - containerRect.left;
    const offsetY = imgRect.top - containerRect.top;
    
    // Calculate scaling factors based on actual image display size vs natural size
    const scaleX = imgRect.width / img.naturalWidth;
    const scaleY = imgRect.height / img.naturalHeight;
    
    return boxes.map((box, idx) => {
      // Convert center coordinates to top-left coordinates
      // Roboflow returns x,y as center coordinates and width,height as dimensions
      const scaledWidth = box.width * scaleX;
      const scaledHeight = box.height * scaleY;
      const left = offsetX + (box.x * scaleX) - (scaledWidth / 2);
      const top = offsetY + (box.y * scaleY) - (scaledHeight / 2);
      
      // Debug logging
      if (debugMode) {
        console.log(`Box ${idx}:`, {
          original: { x: box.x, y: box.y, width: box.width, height: box.height },
          scale: { scaleX, scaleY },
          image: { naturalWidth: img.naturalWidth, naturalHeight: img.naturalHeight, displayWidth: imgRect.width, displayHeight: imgRect.height },
          offset: { offsetX, offsetY },
          calculated: { left, top, width: scaledWidth, height: scaledHeight }
        });
      }
      
      return (
        <div
          key={idx}
          className="bounding-box"
          style={{
            position: 'absolute',
            left: left,
            top: top,
            width: scaledWidth,
            height: scaledHeight,
          }}
        >
          <div className="box-label">
            {box.class} ({(box.confidence * 100).toFixed(1)}%)
            {debugMode && (
              <div style={{ fontSize: '0.6rem', opacity: 0.8 }}>
                {Math.round(left)},{Math.round(top)} {Math.round(scaledWidth)}x{Math.round(scaledHeight)}
              </div>
            )}
          </div>
        </div>
      );
    });
  };

  // Progress component
  const ProgressSteps = () => (
    <div className="progress-steps">
      {steps.map((step, index) => (
        <React.Fragment key={step.id}>
          <div className={`progress-step ${step.completed ? 'completed' : step.active ? 'active' : 'pending'}`}>
            <div className="progress-step-icon">
              {step.completed ? '✓' : step.id}
            </div>
            <span>{step.label}</span>
          </div>
          {index < steps.length - 1 && (
            <div style={{ flex: 1, height: '1px', background: '#e2e8f0', margin: '0 0.5rem' }} />
          )}
        </React.Fragment>
      ))}
    </div>
  );

  return (
    <div className="app-container">
      <h1 className="app-title">Dental X-ray DICOM Analyzer</h1>
      <p className="app-subtitle">AI-Powered Pathology Detection and Diagnostic Reporting</p>
      
      <ProgressSteps />
      
      <div className="main-panel">
        {/* Left Panel: Image Viewer */}
        <div className="left-panel">
          <div className="upload-section">
            <div className="upload-controls">
              <div className="file-input-wrapper">
                <input
                  type="file"
                  accept=".dcm,.rvg"
                  onChange={handleFileChange}
                  disabled={loading}
                  className="file-input"
                  id="file-input"
                />
                <label htmlFor="file-input" className="file-input-button">
                  📁 Choose DICOM File
                </label>
              </div>
              
              <button 
                onClick={handleUpload} 
                disabled={!selectedFile || loading}
                className="btn btn-primary"
              >
                {loading && currentStep === 1 ? (
                  <>
                    <div className="spinner"></div>
                    Uploading...
                  </>
                ) : (
                  <>📤 Upload</>
                )}
              </button>
              
              <button 
                onClick={handlePredict} 
                disabled={!fileId || loading}
                className="btn btn-secondary"
              >
                {loading && currentStep === 2 ? (
                  <>
                    <div className="spinner"></div>
                    Analyzing...
                  </>
                ) : (
                  <>🔍 Detect Pathologies</>
                )}
              </button>
              
              {boxes.length > 0 && (
                <button 
                  onClick={() => setDebugMode(!debugMode)}
                  className="btn btn-outline"
                  style={{ fontSize: '0.7rem', padding: '0.4rem 0.7rem' }}
                >
                  {debugMode ? '🔍 Hide Debug' : '🐛 Debug'}
                </button>
              )}
            </div>
            
            {selectedFile && (
              <div className="selected-file">
                📄 {selectedFile.name}
              </div>
            )}
          </div>
          
          <div className={`image-viewer ${imageUrl ? 'has-image' : ''}`}>
            {imageUrl ? (
              <div className="image-container">
                <img
                  src={imageUrl}
                  alt="DICOM Preview"
                  ref={imageRef}
                  onLoad={() => {
                    // Force re-render of bounding boxes after image loads
                    setTimeout(() => {
                      setBoxes(prev => [...prev]);
                    }, 100);
                  }}
                />
                {renderBoxes()}
              </div>
            ) : (
              <div className="image-placeholder">
                <div className="image-placeholder-icon">🦷</div>
                <div>Upload a DICOM file to begin analysis</div>
              </div>
            )}
          </div>
          
          {boxes.length > 0 && (
            <div className="success-message mt-4">
              ✅ Found {boxes.length} potential patholog{boxes.length === 1 ? 'y' : 'ies'}
            </div>
          )}
        </div>
        
        {/* Right Panel: Report */}
        <div className="right-panel">
          <div className="report-header">
            <h3 className="report-title">Diagnostic Report</h3>
            <button
              onClick={handleReport}
              disabled={!fileId || !boxes.length || loading}
              className="btn btn-success"
            >
              {loading && currentStep === 3 ? (
                <>
                  <div className="spinner"></div>
                  Generating...
                </>
              ) : (
                <>📋 Generate Report</>
              )}
            </button>
          </div>
          
          <div className="report-panel">
            {loading && currentStep === 3 && (
              <div className="loading-overlay">
                <div className="loading-spinner"></div>
                <div className="loading-text">{loadingStep}</div>
              </div>
            )}
            
            {report ? (
              <div className="report-content">{report}</div>
            ) : (
              <div className="report-placeholder">
                <div className="report-placeholder-icon">📄</div>
                <div>
                  {!fileId ? "Upload a DICOM file first" :
                   !boxes.length ? "Run pathology detection first" :
                   "Click 'Generate Report' to create diagnostic analysis"}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Status Messages */}
      {error && (
        <div className="error-message">
          ❌ {error}
        </div>
      )}
      
      {successMessage && (
        <div className="success-message">
          ✅ {successMessage}
        </div>
      )}
    </div>
  );
}

export default App;
