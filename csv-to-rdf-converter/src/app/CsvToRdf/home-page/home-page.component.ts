import { ChangeDetectorRef, ChangeDetectionStrategy, Component } from '@angular/core';
import { RdfConverterService } from '../../services/rdf-converter.service';
import { NgIf } from '@angular/common';

@Component({
  selector: 'app-home-page',
  imports: [NgIf],
  templateUrl: './home-page.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomePageComponent {
  csvFile!: File;
  jsonFile!: File;
  ttlPreview: string = '';
  isProcessing: boolean = false;
  showTooltip = false;

  constructor(
  private converterService: RdfConverterService,
  private cdr: ChangeDetectorRef
) {}

  onCsvSelected(event: any): void {
    this.csvFile = event.target.files[0];
  }

  onJsonSelected(event: any): void {
    this.jsonFile = event.target.files[0];
  }

  convertToRdf(): void {
    if (!this.csvFile || !this.jsonFile) return;

    this.isProcessing = true;
    this.ttlPreview = '';

    this.converterService.convertToRDF(this.csvFile, this.jsonFile).subscribe({
      next: (blob) => {
        const reader = new FileReader();

        reader.onload = () => {
          this.ttlPreview = reader.result as string;
          this.isProcessing = false;
          this.cdr.detectChanges();
        };

        reader.onerror = () => {
          alert('❌ Error al leer el archivo TTL.');
          console.error('FileReader error:', reader.error);
          this.cdr.detectChanges();
          this.isProcessing = false;
        };

        reader.readAsText(blob);
      },

      error: async (err) => {
        console.error('❌ Error al convertir RDF', err);
        this.isProcessing = false;

        if (err.error instanceof Blob) {
          const text = await err.error.text();
          try {
            const json = JSON.parse(text);
            alert('❌ Error del backend:\n' + json.error);
          } catch {
            alert('❌ Error inesperado:\n' + text);
          }
        } else {
          alert('❌ Error general:\n' + err.message || err.statusText);
        }
      },

      complete: () => {
        // No cambia el estado aquí porque ya se hace en `next` o `error`
      },
    });
  }

  downloadTtl(): void {
    if (!this.ttlPreview) return;

    const blob = new Blob([this.ttlPreview], { type: 'text/turtle' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'converted-data.ttl';
    a.click();
    URL.revokeObjectURL(url);
  }
}
