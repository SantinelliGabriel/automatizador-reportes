-- Volcado sintético de una base creada con el código de main (esquema v0).
BEGIN TRANSACTION;
CREATE TABLE comprobantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            importacion_id INTEGER NOT NULL REFERENCES importaciones(id),
            cliente TEXT NOT NULL, periodo TEXT NOT NULL, operacion TEXT NOT NULL,
            fecha TEXT NOT NULL, tipo_comprobante TEXT NOT NULL,
            punto_venta INTEGER NOT NULL, numero INTEGER NOT NULL,
            cuit TEXT NOT NULL, razon_social TEXT NOT NULL,
            neto_gravado_centavos INTEGER NOT NULL, alicuota REAL NOT NULL,
            iva_centavos INTEGER NOT NULL, no_gravado_exento_centavos INTEGER NOT NULL,
            percepciones_centavos INTEGER NOT NULL, total_centavos INTEGER NOT NULL,
            moneda TEXT NOT NULL DEFAULT 'ARS', tipo_cambio REAL NOT NULL DEFAULT 1,
            neto_gravado_origen_centavos INTEGER NOT NULL DEFAULT 0,
            iva_origen_centavos INTEGER NOT NULL DEFAULT 0,
            no_gravado_exento_origen_centavos INTEGER NOT NULL DEFAULT 0,
            percepciones_origen_centavos INTEGER NOT NULL DEFAULT 0,
            total_origen_centavos INTEGER NOT NULL DEFAULT 0,
            detalle_alicuotas_json TEXT NOT NULL DEFAULT '[]',
            UNIQUE(cliente, periodo, operacion, tipo_comprobante, punto_venta, numero, cuit)
        );
INSERT INTO "comprobantes" VALUES(1,1,'Cliente Demo Norte','2026-09','ventas','2026-09-03','A',1,101,'30712345671','Proveedor Sintético Uno',10000000,21.0,2100000,0,0,12100000,'ARS',1.0,10000000,2100000,0,0,12100000,'[{"alicuota": 21.0, "neto_gravado": 100000.0, "iva": 21000.0, "neto_gravado_origen": 100000.0, "iva_origen": 21000.0}]');
INSERT INTO "comprobantes" VALUES(2,1,'Cliente Demo Norte','2026-09','compras','2026-09-08','A',2,44,'30776543213','Cliente Sintético Dos',5000000,10.5,525000,0,0,5525000,'ARS',1.0,5000000,525000,0,0,5525000,'[{"alicuota": 10.5, "neto_gravado": 50000.0, "iva": 5250.0, "neto_gravado_origen": 50000.0, "iva_origen": 5250.0}]');
INSERT INTO "comprobantes" VALUES(3,2,'Cliente Sintético USD','2026-09','ventas','2026-09-15','A',1,501,'30788888887','Entidad Sintética USD',10002500,21.0,2100525,0,0,12103025,'USD',1000.25,10000,2100,0,0,12100,'[{"alicuota": 21.0, "neto_gravado": 100025.0, "iva": 21005.25, "neto_gravado_origen": 100.0, "iva_origen": 21.0}]');
CREATE TABLE importaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_importacion TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            archivo_origen TEXT NOT NULL,
            cliente TEXT NOT NULL DEFAULT '', periodo TEXT NOT NULL DEFAULT '',
            aceptados INTEGER NOT NULL DEFAULT 0, rechazados INTEGER NOT NULL DEFAULT 0,
            cantidad_ventas INTEGER NOT NULL DEFAULT 0, total_centavos INTEGER NOT NULL DEFAULT 0
        );
INSERT INTO "importaciones" VALUES(1,'2026-10-22 20:54:01','Cliente Demo Norte.xlsx','Cliente Demo Norte','2026-09',2,0,2,17625000);
INSERT INTO "importaciones" VALUES(2,'2026-10-22 20:54:01','Cliente Sintético USD.csv','Cliente Sintético USD','2026-09',1,0,1,12103025);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('importaciones',2);
INSERT INTO "sqlite_sequence" VALUES('comprobantes',3);
COMMIT;
