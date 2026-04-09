import { useRef, useState } from 'react';

export default function UploadBox({ onFileSelected, previewUrl, onClear }) {
  const fileRef = useRef(null);
  const [dragOver, setDragOver] = useState(false);

  const acceptFile = (file) => {
    if (!file || !file.type.startsWith('image/')) return;
    onFileSelected(file);
  };

  return (
    <div className="glass-card">
      <div
        className={`upload-dropzone ${dragOver ? 'is-over' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          acceptFile(e.dataTransfer.files?.[0]);
        }}
        onClick={() => fileRef.current?.click()}
      >
        <div className="upload-title">Upload Medicine Image</div>
        <div className="upload-subtitle">Drag and drop or click to browse</div>
        <div className="upload-chips">
          {['JPG', 'PNG', 'WEBP', 'BMP'].map((chip) => (
            <span key={chip} className="chip">{chip}</span>
          ))}
        </div>
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(e) => acceptFile(e.target.files?.[0])}
      />

      {previewUrl && (
        <div className="preview-wrap">
          <img src={previewUrl} alt="medicine preview" className="preview-image" />
          <button className="btn btn-danger" onClick={onClear}>Clear</button>
        </div>
      )}
    </div>
  );
}
