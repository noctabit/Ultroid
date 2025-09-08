# Configuración de SQLite para Ultroid

## Descripción

Ultroid ahora soporta SQLite como opción de base de datos, proporcionando una alternativa ligera y local que no requiere configuración de servidores externos.

## Configuración

### 1. Variable de Entorno

Para usar SQLite como base de datos, añade la siguiente variable de entorno:

```bash
SQLITE_PATH=ultroid.db
```

O si prefieres una ruta específica:

```bash
SQLITE_PATH=/path/to/your/database.db
```

### 2. En archivo .env

```env
SQLITE_PATH=ultroid.db
```

### 3. Prioridad de Base de Datos

El orden de prioridad para la selección de base de datos es:

1. **Redis** - Si `REDIS_URI` o `REDISHOST` están configurados
2. **MongoDB** - Si `MONGO_URI` está configurado  
3. **PostgreSQL** - Si `DATABASE_URL` está configurado
4. **SQLite** - Si `SQLITE_PATH` está configurado
5. **LocalDB** - Como fallback por defecto

## Ventajas de SQLite

- ✅ **Sin configuración de servidor**: No necesitas configurar Redis, MongoDB o PostgreSQL
- ✅ **Ligero y rápido**: Base de datos embebida con excelente rendimiento
- ✅ **Persistente**: Los datos se mantienen entre reinicios
- ✅ **Sin dependencias externas**: SQLite está incluido en Python
- ✅ **Fácil backup**: Solo copia el archivo de base de datos

## Funcionalidades Soportadas

- ✅ Almacenamiento y recuperación de configuraciones
- ✅ Caché de datos
- ✅ Gestión de claves/valores
- ✅ Transacciones ACID
- ✅ Limpieza completa de datos (`flushall`)

## Ejemplo de Uso

```python
# El userbot automáticamente usará SQLite si está configurado
# No se requiere código adicional
```

## Notas Importantes

- El archivo de base de datos se creará automáticamente si no existe
- Asegúrate de que el directorio especificado en `SQLITE_PATH` existe y tiene permisos de escritura
- Para hacer backup, simplemente copia el archivo `.db`
- SQLite es thread-safe y puede manejar múltiples conexiones concurrentes

## Migración desde otras Bases de Datos

Si quieres migrar desde Redis/MongoDB/PostgreSQL a SQLite:

1. Configura `SQLITE_PATH` en tu `.env`
2. Reinicia el userbot
3. Los datos anteriores se mantendrán en la base de datos original
4. Los nuevos datos se almacenarán en SQLite

Para migrar datos existentes, usa los comandos de backup/restore del userbot.