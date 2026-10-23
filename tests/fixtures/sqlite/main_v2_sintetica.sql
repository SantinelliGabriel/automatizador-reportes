BEGIN TRANSACTION;
CREATE TABLE "comprobantes" (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        importacion_id INTEGER NOT NULL REFERENCES importaciones(id),
        cliente TEXT NOT NULL, periodo TEXT NOT NULL, operacion TEXT NOT NULL,
        fecha TEXT NOT NULL, tipo_comprobante TEXT NOT NULL,
        punto_venta INTEGER NOT NULL, numero INTEGER NOT NULL,
        cuit TEXT NOT NULL, razon_social TEXT NOT NULL,
        neto_gravado_centavos INTEGER NOT NULL, alicuota TEXT NOT NULL,
        iva_centavos INTEGER NOT NULL, no_gravado_exento_centavos INTEGER NOT NULL,
        percepciones_centavos INTEGER NOT NULL, total_centavos INTEGER NOT NULL,
        moneda TEXT NOT NULL DEFAULT 'ARS', tipo_cambio TEXT NOT NULL DEFAULT '1',
        neto_gravado_origen_centavos INTEGER NOT NULL DEFAULT 0,
        iva_origen_centavos INTEGER NOT NULL DEFAULT 0,
        no_gravado_exento_origen_centavos INTEGER NOT NULL DEFAULT 0,
        percepciones_origen_centavos INTEGER NOT NULL DEFAULT 0,
        total_origen_centavos INTEGER NOT NULL DEFAULT 0,
        detalle_alicuotas_json TEXT NOT NULL DEFAULT '[]',
        revision_decimal TEXT NOT NULL DEFAULT '',
        UNIQUE(cliente, periodo, operacion, tipo_comprobante, punto_venta, numero, cuit)
    );
INSERT INTO "comprobantes" VALUES(3,3,'Cliente Sintético','2026-09','ventas','2026-09-03','A',1,3,'30712345671','Empresa Sintética',10000000,'21',2100000,0,0,12100000,'ARS','1',10000000,2100000,0,0,12100000,'[{"alicuota": "21", "neto_gravado": "100000.00", "iva": "21000.00", "neto_gravado_origen": "100000.00", "iva_origen": "21000.00"}]','');
INSERT INTO "comprobantes" VALUES(4,3,'Cliente Sintético','2026-09','compras','2026-09-03','A',1,4,'30712345671','Empresa Sintética',10000000,'21',2100000,0,0,12100000,'ARS','1',10000000,2100000,0,0,12100000,'[{"alicuota": "21", "neto_gravado": "100000.00", "iva": "21000.00", "neto_gravado_origen": "100000.00", "iva_origen": "21000.00"}]','');
CREATE TABLE importaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_importacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            archivo_origen TEXT NOT NULL,
            sha256 TEXT NOT NULL DEFAULT '',
            cliente TEXT NOT NULL DEFAULT '', periodo TEXT NOT NULL DEFAULT '',
            aceptados INTEGER NOT NULL DEFAULT 0, rechazados INTEGER NOT NULL DEFAULT 0,
            cantidad_ventas INTEGER NOT NULL DEFAULT 0, total_centavos INTEGER NOT NULL DEFAULT 0
        );
INSERT INTO "importaciones" VALUES(1,'2026-10-22 21:45:26','ventas.csv','','Cliente Sintético','2026-09',1,0,1,12100000);
INSERT INTO "importaciones" VALUES(2,'2026-10-22 21:45:26','compras.csv','','Cliente Sintético','2026-09',1,0,1,12100000);
INSERT INTO "importaciones" VALUES(3,'2026-10-22 21:45:26','mixto.csv','','Cliente Sintético','2026-09',2,0,2,24200000);
INSERT INTO "importaciones" VALUES(4,'2026-10-22 21:45:26','observado.csv','','Cliente Sintético','2026-09',0,1,0,0);
CREATE TABLE observaciones (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        importacion_id INTEGER NOT NULL REFERENCES importaciones(id),
        fila_excel TEXT NOT NULL DEFAULT '', motivo TEXT NOT NULL,
        datos_json TEXT NOT NULL DEFAULT '{}'
    );
INSERT INTO "observaciones" VALUES(1,4,'2','CUIT inválido: formato o dígito verificador incorrecto.','{"fecha": "2026-09-03", "tipo_comprobante": "A", "punto_venta": "1", "numero": "5", "cuit": "", "razon_social": "Empresa Sintética", "operacion": "ventas", "neto_gravado": "100000.00", "alicuota": "21", "iva": "21000.00", "no_gravado_exento": "0.00", "percepciones": "0.00", "total": "121000.00", "neto_gravado_origen": "100000.00", "iva_origen": "21000.00", "no_gravado_exento_origen": "0.00", "percepciones_origen": "0.00", "total_origen": "121000.00", "moneda": "ARS", "tipo_cambio": "1", "detalle_alicuotas": "[{\"alicuota\": \"21\", \"neto_gravado\": \"100000.00\", \"iva\": \"21000.00\", \"neto_gravado_origen\": \"100000.00\", \"iva_origen\": \"21000.00\"}]"}');
CREATE INDEX idx_observaciones_importacion ON observaciones(importacion_id);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('importaciones',4);
INSERT INTO "sqlite_sequence" VALUES('comprobantes',4);
INSERT INTO "sqlite_sequence" VALUES('observaciones',1);
COMMIT;
PRAGMA user_version = 2;
